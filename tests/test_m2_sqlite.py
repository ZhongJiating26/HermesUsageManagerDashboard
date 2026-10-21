import importlib
import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from dashboard.plugin_api import api
from dev.seed_sqlite import mock_runtime, seed

db = importlib.import_module(api.__package__ + '.db')
events = importlib.import_module(api.__package__ + '.events')
schemas = importlib.import_module(api.__package__ + '.schemas')
admin = importlib.import_module(api.__package__ + '.admin')
queries = importlib.import_module(api.__package__ + '.queries')
security = importlib.import_module(api.__package__ + '.security')
Principal = security.Principal
PREFIX = '/api/plugins/hermes-usage-manager'
RANGE = {'from': '2026-10-09', 'to': '2026-10-16', 'tz': 'Asia/Shanghai'}
ADMIN = Principal('test-admin', 'admin')


@pytest.fixture
def runtime(tmp_path):
    return api.Runtime(db.Store(tmp_path / 'live.sqlite3'))


@pytest.fixture
def client(runtime):
    app = FastAPI()
    app.state.hum_runtime = runtime
    app.dependency_overrides[api.get_runtime] = lambda: runtime

    def principal(request: Request):
        role = request.headers.get('test-role', 'admin')
        return Principal('test-' + role, role, 'd1' if role == 'department' else None, 'u1' if role == 'user' else None)

    app.dependency_overrides[api.get_principal] = principal
    app.include_router(api.router, prefix=PREFIX)
    with TestClient(app) as session:
        yield session


def model(identifier='one', **overrides):
    return events.ModelEvent(**({'instance_id': 'i1', 'profile_id': 'p1', 'source_event_id': identifier, 'api_request_id': identifier, 'session_id': 's1', 'provider': 'Test', 'model': 'model-a', 'occurred_at': '2026-10-15T00:00:00+08:00', 'input_total_tokens': 100, 'cached_input_tokens': 30, 'output_tokens': 20} | overrides))


def price(**overrides):
    return schemas.PriceBody(**({'provider': 'Test', 'model': 'model-a', 'input': '2', 'cached': '0.5', 'output': '4', 'valid_from': '2026-10-01', 'valid_to': '2026-10-15'} | overrides))


def insert(runtime, event):
    with runtime.store.transaction() as connection:
        return events.ingest_model(connection, event)


def test_migrations_persist_and_reject_mode_or_checksum_changes(tmp_path):
    path = tmp_path / 'usage.sqlite3'
    store = db.Store(path, 'mock')
    with store.transaction() as connection:
        connection.execute("INSERT INTO departments(id,name) VALUES('d1','Persistent')")
    reopened = db.Store(path, 'mock')
    with reopened.read() as connection:
        assert connection.execute('SELECT count(*) FROM schema_migrations').fetchone()[0] == 5
        assert connection.execute('SELECT name FROM departments').fetchone()[0] == 'Persistent'
        assert connection.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        assert connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    with pytest.raises(ValueError, match='mode mismatch'):
        db.Store(path, 'live')
    with store.transaction() as connection:
        connection.execute("UPDATE schema_migrations SET checksum='tampered' WHERE version='0001_init'")
    with pytest.raises(ValueError, match='checksum'):
        db.Store(path, 'mock')


def test_path_guard_and_future_schema(tmp_path):
    with pytest.raises(ValueError, match='absolute'):
        db.Store('relative.sqlite3')
    with pytest.raises(ValueError, match='outside'):
        db.Store(db.PLUGIN_ROOT / 'bad.sqlite3')
    store = db.Store(tmp_path / 'schema.sqlite3')
    with store.transaction() as connection:
        connection.execute("INSERT INTO schema_migrations VALUES('9999_future','x','now')")
    with pytest.raises(ValueError, match='newer'):
        db.Store(store.path)


def test_transaction_rollback_and_bounded_busy_timeout(runtime):
    with pytest.raises(RuntimeError):
        with runtime.store.transaction() as connection:
            connection.execute("INSERT INTO departments VALUES('d1','Rollback','active')")
            raise RuntimeError('rollback')
    with runtime.store.read() as connection:
        assert connection.execute('SELECT count(*) FROM departments').fetchone()[0] == 0
    started = time.monotonic()
    with runtime.store.transaction():
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            with runtime.store.transaction():
                pass
    assert 2 <= time.monotonic() - started < 6


def test_cache_subset_total_and_integer_cost_are_frozen(runtime):
    with runtime.store.transaction() as connection:
        price_id = admin.save_price(connection, ADMIN, price())
        events.ingest_model(connection, model())
    with runtime.store.read() as connection:
        before = dict(connection.execute('SELECT * FROM llm_requests').fetchone())
    assert (before['uncached_input_tokens'], before['cached_input_tokens'], before['total_tokens']) == (70, 30, 120)
    assert before['cost_micro_usd'] == 235
    assert before['cost_source'] == 'estimated'
    with runtime.store.transaction() as connection:
        admin.save_price(connection, ADMIN, price(input='20'), price_id)
        events.ingest_model(connection, model('two'))
    with runtime.store.read() as connection:
        after = dict(connection.execute('SELECT * FROM llm_requests WHERE source_event_id=?', ('one',)).fetchone())
        newer = dict(connection.execute('SELECT * FROM llm_requests WHERE source_event_id=?', ('two',)).fetchone())
        assert before == after
        assert newer['price_revision_id'] != before['price_revision_id']
        assert newer['cost_micro_usd'] == 1495


@pytest.mark.parametrize('fields,total', [({'cached_input_tokens': None}, 120), ({'output_tokens': None}, None), ({'input_total_tokens': None, 'cached_input_tokens': None}, None)])
def test_unknown_fields_are_not_zero_or_estimated(runtime, fields, total):
    with runtime.store.transaction() as connection:
        admin.save_price(connection, ADMIN, price())
        events.ingest_model(connection, model(**fields))
    with runtime.store.read() as connection:
        row = connection.execute('SELECT * FROM llm_requests').fetchone()
        assert row['cost_micro_usd'] is None
        assert row['total_tokens'] == total
        if fields.get('cached_input_tokens', 0) is None:
            assert row['uncached_input_tokens'] is None


def test_replay_three_times_and_cross_profile_collision(runtime):
    for _ in range(3):
        insert(runtime, model())
    insert(runtime, model(profile_id='p2'))
    insert(runtime, model(instance_id='i2'))
    with runtime.store.read() as connection:
        assert connection.execute('SELECT count(*) FROM llm_requests').fetchone()[0] == 3
        assert connection.execute('SELECT count(*) FROM sessions').fetchone()[0] == 3
        assert connection.execute('SELECT count(*) FROM event_inbox').fetchone()[0] == 3
    reopened = api.Runtime(db.Store(runtime.store.path))
    assert insert(reopened, model()) is False


def test_price_date_boundary_overlap_and_gaps(runtime, client):
    with runtime.store.transaction() as connection:
        price_id = admin.save_price(connection, ADMIN, price(valid_from='2026-10-15', valid_to='2026-10-15'))
        for identifier, timestamp in [('before', '2026-10-14T23:59:59+08:00'), ('start', '2026-10-15T00:00:00+08:00'), ('end', '2026-10-15T23:59:59+08:00'), ('after', '2026-10-16T00:00:00+08:00')]:
            events.ingest_model(connection, model(identifier, occurred_at=timestamp))
    with runtime.store.read() as connection:
        costs = {row['source_event_id']: row['cost_micro_usd'] for row in connection.execute('SELECT * FROM llm_requests')}
        assert costs == {'before': None, 'start': 235, 'end': 235, 'after': None}
        gaps = admin.unpriced(connection)
        assert [(row['valid_from'], row['valid_to']) for row in gaps] == [('2026-10-14', '2026-10-14'), ('2026-10-16', '2026-10-16')]
    assert client.post(PREFIX + '/models/prices', json=price(valid_from='2026-10-15', valid_to=None).model_dump(mode='json')).status_code == 409
    assert client.post(PREFIX + '/models/prices', json=price(valid_from='2026-10-16', valid_to=None).model_dump(mode='json')).status_code == 200
    assert client.patch(PREFIX + '/models/prices/' + price_id, json=price(valid_from='2026-10-15', valid_to='2026-10-14').model_dump(mode='json')).status_code == 422


def test_price_validation_and_failed_usage(client, runtime):
    body = price().model_dump(mode='json')
    for bad in [-1, 'NaN', 'Infinity', '0.0000001']:
        assert client.post(PREFIX + '/models/prices', json=body | {'input': bad}).status_code == 422
    with pytest.raises(ValidationError):
        model(cached_input_tokens=101)
    insert(runtime, model(status='failed', input_total_tokens=None, cached_input_tokens=None, output_tokens=None, error_code='timeout'))
    payload = client.get(PREFIX + '/overview/summary', params=RANGE).json()['data']
    assert payload['count'] == 1
    assert payload['kpis']['failed_requests'] == 1
    assert payload['kpis']['total_tokens'] is None
    assert payload['kpis']['cost'] is None


def test_identity_uses_external_id_and_historical_department_not_name(runtime):
    with runtime.store.transaction() as connection:
        connection.execute("INSERT INTO departments VALUES('d1','Old','active')")
        connection.execute("INSERT INTO departments VALUES('d2','New','active')")
        connection.execute("INSERT INTO users(id,name,external_id,department_id) VALUES('u1','not-an-id','external-1','d2')")
        connection.execute("INSERT INTO department_membership VALUES('old','u1','d1','2026-10-01T00:00:00.000000+00:00','2026-10-16T00:00:00.000000+00:00')")
        connection.execute("INSERT INTO department_membership VALUES('new','u1','d2','2026-10-16T00:00:00.000000+00:00',NULL)")
        events.ingest_model(connection, model(external_user_id='external-1', platform='feishu'))
        events.ingest_model(connection, model('unknown', external_user_id='not-an-id', platform='feishu'))
        rows = {row['source_event_id']: dict(row) for row in connection.execute('SELECT * FROM llm_requests')}
    assert rows['one']['user_id'] == 'u1'
    assert rows['one']['department_id'] == 'd1'
    assert rows['unknown']['identity_status'] == 'unresolved'
    assert rows['unknown']['user_id'] is None


def test_explicit_profile_mapping_is_not_assumed_from_display_field(runtime):
    with runtime.store.transaction() as connection:
        connection.execute("INSERT INTO users(id,name,external_id,profile) VALUES('u1','User','e1','p1')")
        events.ingest_model(connection, model())
        connection.execute("INSERT INTO profile_user_mapping VALUES('i1','p1','u1','2026-01-01T00:00:00.000000+00:00',NULL)")
        events.ingest_model(connection, model('mapped'))
        assert connection.execute("SELECT user_id FROM llm_requests WHERE source_event_id='one'").fetchone()[0] is None
        assert connection.execute("SELECT user_id FROM llm_requests WHERE source_event_id='mapped'").fetchone()[0] == 'u1'


def test_mcp_classification_server_identity_and_tool_only_activity(runtime, client):
    with runtime.store.transaction() as connection:
        for index, (kind, server) in enumerate([('mcp', 'a'), ('mcp', 'b'), ('local', None), ('unknown', None), ('mcp', None)]):
            event = events.ToolEvent(instance_id='i1', profile_id='p1', source_event_id=str(index), session_id='s1', tool_id='same', tool_name='same-name', tool_type=kind, mcp_server_id=server, user_id='u1', occurred_at='2026-10-15T00:00:00+08:00')
            for _ in range(3):
                events.ingest_tool(connection, event)
    payload = client.get(PREFIX + '/overview/summary', params=RANGE).json()['data']
    assert {row['id'] for row in payload['tools']} == {'a:same', 'b:same'}
    assert payload['kpis']['active'] == 1
    assert sum(day['calls'] for day in payload['trend']) == 2
    filtered = client.get(PREFIX + '/mcp/tools/ranking', params=RANGE | {'server_id': 'a'}).json()['data']
    assert len(filtered) == 1 and filtered[0]['calls'] == 1


def test_department_move_preserves_events_and_rolls_back_invalid_batch(runtime, client):
    with runtime.store.transaction() as connection:
        for department in ('d1', 'd2'):
            connection.execute('INSERT INTO departments(id,name) VALUES(?,?)', (department, department))
        connection.execute("INSERT INTO users(id,name,external_id,department_id) VALUES('u1','User','e1','d1')")
        connection.execute("INSERT INTO department_membership VALUES('initial','u1','d1','2026-01-01T00:00:00.000000+00:00',NULL)")
        events.ingest_model(connection, model(user_id='u1', department_id='d1'))
    assert client.post(PREFIX + '/people/assignments/move', json={'user_ids': ['u1', 'missing'], 'department_id': 'd2'}).status_code == 422
    assert client.post(PREFIX + '/people/assignments/move', json={'user_ids': ['u1'], 'department_id': 'd2'}).status_code == 200
    assert client.delete(PREFIX + '/people/departments/d2').status_code == 409
    assert client.delete(PREFIX + '/people/departments/d1').status_code == 200
    with runtime.store.read() as connection:
        assert connection.execute('SELECT department_id FROM llm_requests').fetchone()[0] == 'd1'
        assert connection.execute('SELECT department_id FROM users').fetchone()[0] == 'd2'
        assert connection.execute('SELECT count(*) FROM department_membership').fetchone()[0] == 2


def test_unassign_department_closes_membership_without_rewriting_history(runtime, client):
    with runtime.store.transaction() as c:
        c.execute("INSERT INTO departments(id,name) VALUES('d1','One')")
        c.execute("INSERT INTO users(id,name,external_id,department_id) VALUES('u1','User','e1','d1')")
        c.execute("INSERT INTO department_membership VALUES('initial','u1','d1','2026-01-01T00:00:00.000000+00:00',NULL)")
        events.ingest_model(c, model(user_id='u1', department_id='d1'))
    path = PREFIX + '/people/assignments/move'
    assert client.post(path, json={'user_ids': ['u1', 'missing'], 'department_id': ''}).status_code == 422
    assert client.post(path, json={'user_ids': ['u1'], 'department_id': ''}).status_code == 200
    assert client.post(path, json={'user_ids': ['u1'], 'department_id': ''}).status_code == 200
    with runtime.store.read() as c:
        assert c.execute('SELECT department_id FROM users').fetchone()[0] is None
        assert c.execute('SELECT valid_to FROM department_membership').fetchone()[0] is not None
        assert c.execute('SELECT count(*) FROM department_membership').fetchone()[0] == 1
        assert c.execute('SELECT department_id FROM llm_requests').fetchone()[0] == 'd1'
    assert client.get(PREFIX + '/people/users').json()['data'][0]['department_id'] == ''
    assert client.post(path, json={'user_ids': ['u1'], 'department_id': 'd1'}).status_code == 200
    with runtime.store.read() as c:
        assert c.execute('SELECT department_id FROM users').fetchone()[0] == 'd1'
        assert c.execute('SELECT count(*) FROM department_membership WHERE valid_to IS NULL').fetchone()[0] == 1


def test_create_and_edit_user_without_department(runtime, client):
    body = {'name': 'Unassigned', 'external_id': 'external-unassigned', 'profile': 'p1', 'department_id': ''}
    response = client.post(PREFIX + '/people/users', json=body)
    assert response.status_code == 200
    user_id = response.json()['data']['id']
    assert client.patch(PREFIX + '/people/users/' + user_id, json=body | {'name': 'Updated'}).status_code == 200
    with runtime.store.read() as c:
        assert c.execute('SELECT department_id FROM users WHERE id=?', (user_id,)).fetchone()[0] is None
        assert c.execute('SELECT count(*) FROM department_membership').fetchone()[0] == 0


@pytest.mark.parametrize('role', ['department', 'user'])
def test_scope_and_all_sensitive_routes_enforce_server_permissions(runtime, client, role):
    insert(runtime, model(user_id='u1', department_id='d1'))
    insert(runtime, model('other', user_id='u2', department_id='d2'))
    headers = {'test-role': role}
    result = client.get(PREFIX + '/requests', params=RANGE, headers=headers).json()
    assert result['meta']['total'] == 1
    assert result['data'][0]['user_id'] == 'u1'
    assert client.get(PREFIX + '/requests', params=RANGE | {'department_id': 'd2'}, headers=headers).json()['meta']['total'] == 0
    for path in ['/sessions', '/people/users', '/people/departments', '/models/prices', '/models/unpriced', '/audit/access-logs', '/settings']:
        assert client.get(PREFIX + path, params=RANGE, headers=headers).status_code == 403
    assert client.post(PREFIX + '/people/departments', json={'name': 'forbidden'}, headers=headers).status_code == 403


def test_production_never_trusts_mock_headers_or_query_roles(runtime, monkeypatch):
    monkeypatch.delenv('USAGE_MANAGER_TRUST_DASHBOARD_ADMIN', raising=False)
    app = FastAPI()
    app.dependency_overrides[api.get_runtime] = lambda: runtime
    app.include_router(api.router, prefix=PREFIX)
    response = TestClient(app).get(PREFIX + '/requests?role=admin', params=RANGE, headers={'x-hum-mock-role': 'admin', 'x-role': 'admin'})
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'IDENTITY_UNAVAILABLE'
    assert 'request_id' in response.json()['error']


def test_timeline_unavailable_is_audited_without_fabricated_text(runtime, client):
    insert(runtime, model())
    session_id = events.key('i1', 'p1', 's1')
    response = client.get(PREFIX + f'/sessions/{session_id}/timeline', params=RANGE)
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'SESSION_CONTENT_UNAVAILABLE'
    with runtime.store.read() as connection:
        assert connection.execute('SELECT result FROM audit_access_logs').fetchone()[0] == 'unavailable'
    assert client.get(PREFIX + f'/sessions/{session_id}', params=RANGE).status_code == 200
    assert client.get(PREFIX + '/sessions/missing', params=RANGE).status_code == 404


def test_timezone_midnight_dst_and_exclusive_end(runtime, client):
    insert(runtime, model('before', occurred_at='2026-10-14T15:59:59+00:00'))
    insert(runtime, model('after', occurred_at='2026-10-14T16:00:00+00:00'))
    response = client.get(PREFIX + '/requests', params={'from': '2026-10-15', 'to': '2026-10-16', 'tz': 'Asia/Shanghai'}).json()
    assert response['meta']['total'] == 1
    window = schemas.Window('2026-11-01', '2026-11-02', 'America/New_York')
    from datetime import datetime
    assert (datetime.fromisoformat(window.end) - datetime.fromisoformat(window.start)).total_seconds() == 25 * 3600
    assert client.get(PREFIX + '/requests', params=RANGE | {'tz': 'Bogus/Zone'}).status_code == 422


def test_pagination_query_validation_and_index_usage(runtime, client):
    for index in range(25):
        insert(runtime, model(str(index)))
    first = client.get(PREFIX + '/requests', params=RANGE | {'page_size': 20}).json()
    second = client.get(PREFIX + '/requests', params=RANGE | {'page_size': 20, 'page': 2}).json()
    assert first['meta']['total'] == 25
    assert len(second['data']) == 5
    assert {row['id'] for row in first['data']}.isdisjoint(row['id'] for row in second['data'])
    for invalid in [{'page_size': 101}, {'page': 0}, {'sort': 'drop table'}, {'order': 'evil'}]:
        response = client.get(PREFIX + '/requests', params=RANGE | invalid)
        assert response.status_code == 422
        assert set(response.json()['error']) == {'code', 'message', 'request_id'}
    with runtime.store.read() as connection:
        plan = connection.execute('EXPLAIN QUERY PLAN SELECT * FROM llm_requests WHERE department_id=? AND occurred_at>=? AND occurred_at<?', ('d1', 'a', 'z')).fetchall()
        assert 'request_department' in str([tuple(row) for row in plan])


def test_export_opt_in_scope_and_formula_injection(runtime, client):
    insert(runtime, model(provider='=danger', user_id='u1', department_id='d1'))
    insert(runtime, model('other', provider='Other', user_id='u2', department_id='d2'))
    assert client.get(PREFIX + '/exports/requests.csv', params=RANGE).status_code == 403
    assert client.patch(PREFIX + '/settings', json={'export_enabled': True}).status_code == 200
    response = client.get(PREFIX + '/exports/requests.csv', params=RANGE, headers={'test-role': 'department'})
    assert response.status_code == 200
    assert "'=danger" in response.text
    assert 'Other' not in response.text


def test_mock_seed_survives_restart_and_never_seeds_live(tmp_path):
    path = tmp_path / 'mock.sqlite3'
    runtime = mock_runtime(path)
    with runtime.store.transaction() as connection:
        connection.execute("INSERT INTO departments(id,name) VALUES('custom','Keep me')")
    restarted = mock_runtime(path)
    with restarted.store.read() as connection:
        assert connection.execute('SELECT count(*) FROM llm_requests').fetchone()[0] == 1080
        assert connection.execute("SELECT name FROM departments WHERE id='custom'").fetchone()[0] == 'Keep me'
    with pytest.raises(ValueError, match='Mock'):
        seed(db.Store(tmp_path / 'live.sqlite3'))


def test_membership_rejects_overlaps_at_database_boundary(runtime):
    with runtime.store.transaction() as connection:
        connection.execute("INSERT INTO departments(id,name) VALUES('d1','Dept')")
        connection.execute("INSERT INTO users(id,name,external_id) VALUES('u1','User','e1')")
        connection.execute("INSERT INTO department_membership VALUES('one','u1','d1','2026-10-01T00:00:00.000000+00:00','2026-10-15T00:00:00.000000+00:00')")
    with pytest.raises(sqlite3.IntegrityError, match='Overlapping'):
        with runtime.store.transaction() as connection:
            connection.execute("INSERT INTO department_membership VALUES('two','u1','d1','2026-10-14T00:00:00.000000+00:00',NULL)")
    with runtime.store.transaction() as connection:
        connection.execute("INSERT INTO department_membership VALUES('two','u1','d1','2026-10-15T00:00:00.000000+00:00',NULL)")


def test_attempts_are_distinct_and_auxiliary_activity_is_explicit(runtime, client):
    insert(runtime, model('api-1:attempt-0:failed', api_request_id='api-1', status='failed', input_total_tokens=None, cached_input_tokens=None, output_tokens=None))
    insert(runtime, model('api-1:attempt-1:success', api_request_id='api-1', attempt_no=1))
    insert(runtime, model('aux-1', request_kind='auxiliary'))
    payload = client.get(PREFIX + '/overview/kpis', params=RANGE).json()['data']
    assert payload['failed_requests'] == 1
    assert payload['successful_requests'] == 2
    assert payload['auxiliary_requests'] == 1


def test_management_pagination_includes_totals_and_does_not_truncate(client):
    for index in range(102):
        assert client.post(PREFIX + '/people/departments', json={'name': f'department-{index:03d}'}).status_code == 200
    first = client.get(PREFIX + '/people/departments', params={'sort': 'name'}).json()
    second = client.get(PREFIX + '/people/departments', params={'sort': 'name', 'page': 2}).json()
    assert first['meta']['total'] == 102
    assert len(first['data']) == 100 and len(second['data']) == 2
    assert second['data'][0]['name'] == 'department-100'


def test_native_auth_adapter_is_opt_in_fail_closed_and_checks_origin(runtime, monkeypatch):
    adapter = importlib.import_module(api.__package__ + '.adapters.hermes')
    monkeypatch.setenv('USAGE_MANAGER_TRUST_DASHBOARD_ADMIN', '1')
    monkeypatch.setattr(adapter, 'require_dashboard_admin', lambda request: None)
    app = FastAPI()
    app.dependency_overrides[api.get_runtime] = lambda: runtime
    app.include_router(api.router, prefix=PREFIX)
    session = TestClient(app)
    assert session.get(PREFIX + '/people/users').status_code == 200
    assert session.post(PREFIX + '/people/departments', json={'name': 'bad'}, headers={'origin': 'https://other.invalid'}).status_code == 403
    assert session.post(PREFIX + '/people/departments', json={'name': 'ok'}, headers={'origin': 'http://testserver'}).status_code == 200
    def unavailable(request):
        raise HTTPException(503, {'code': 'HOST_AUTH_UNAVAILABLE', 'message': 'Not verified'})
    monkeypatch.setattr(adapter, 'require_dashboard_admin', unavailable)
    assert session.get(PREFIX + '/people/users').json()['error']['code'] == 'HOST_AUTH_UNAVAILABLE'
