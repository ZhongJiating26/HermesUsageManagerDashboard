import importlib
import json
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.plugin_api import api
from tests.test_m2_sqlite import ADMIN, PREFIX, RANGE, db, events, insert, model

collector_module = importlib.import_module(api.__package__ + '.collector')
hooks = importlib.import_module(api.__package__ + '.adapters.hooks')
content = importlib.import_module(api.__package__ + '.adapters.session_content')
quality = importlib.import_module(api.__package__ + '.quality')


def payload(**extra):
    return {'session_id': 's1', 'turn_id': 't1', 'api_request_id': 'api-1', 'provider': 'openai', 'model': 'model-a', 'platform': 'feishu', 'api_call_count': 1, 'started_at': 1791993600.0, 'ended_at': 1791993601.25, 'usage': {'input_tokens': 70, 'cache_read_tokens': 30, 'cache_write_tokens': 0, 'prompt_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}, **extra}


@pytest.fixture
def scope(tmp_path):
    return hooks.HookContext('i1', 'p1', str(tmp_path / 'usage.sqlite3'))


def test_hook_adapter_cache_semantics_ids_and_sensitive_field_allowlist(scope):
    normalizer = hooks.Normalizer()
    normalizer.normalize('pre_llm_call', payload(sender_id='ou-test', user_message='DO_NOT_STORE', conversation_history=[{'content': 'SECRET'}]), scope)
    event = normalizer.normalize('post_api_request', payload(response={'api_key': 'SECRET'}, assistant_message='DO_NOT_STORE', base_url='https://secret@host'), scope)
    assert (event.input_total_tokens, event.cached_input_tokens, event.output_tokens) == (100, 30, 20)
    assert event.external_user_id == 'ou-test'
    assert event.duration_ms == 1250
    serialized = event.model_dump_json()
    assert all(value not in serialized for value in ['DO_NOT_STORE', 'SECRET', 'secret@host', 'base_url'])
    assert normalizer.normalize('post_api_request', payload(), scope).source_event_id == event.source_event_id
    assert normalizer.normalize('api_request_error', payload(retry_count=0, error={'message': 'SECRET'}, status_code=429), scope).error_code == 'HTTP_429'


@pytest.mark.parametrize('usage', [None, {'input_tokens': 100, 'output_tokens': 20}, {'prompt_tokens': 100, 'completion_tokens': 20}, {'input_tokens': 70, 'cache_read_tokens': -1, 'cache_write_tokens': 0, 'prompt_tokens': 100, 'output_tokens': 20}])
def test_unknown_usage_schema_does_not_fabricate_zeros(scope, usage):
    event = hooks.Normalizer().normalize('post_api_request', payload(usage=usage), scope)
    assert event.input_total_tokens is None and event.cached_input_tokens is None
    assert event.output_tokens is None and event.pricing_supported is False


def test_canonical_zero_cache_and_unsupported_cache_write(scope):
    values = payload()['usage'] | {'input_tokens': 100, 'cache_read_tokens': 0, 'prompt_tokens': 100}
    event = hooks.Normalizer().normalize('post_api_request', payload(usage=values), scope)
    assert event.input_total_tokens == 100 and event.cached_input_tokens == 0
    values = payload()['usage'] | {'cache_write_tokens': 10, 'prompt_tokens': 110}
    event = hooks.Normalizer().normalize('post_api_request', payload(usage=values), scope)
    assert event.input_total_tokens == 110 and event.cache_write_tokens == 10
    assert event.pricing_supported is False


@pytest.mark.parametrize('input_tokens,output_tokens', [(100, 20), (100, 0), (0, 20), (0, 0)])
def test_explicit_zero_usage_reaches_storage_prices_and_quality(scope, input_tokens, output_tokens):
    from tests.test_m2_sqlite import admin, price, schemas
    store = db.Store(scope.db_path)
    values = {'input_tokens': input_tokens, 'cache_read_tokens': 0,
              'cache_write_tokens': 0, 'prompt_tokens': input_tokens,
              'output_tokens': output_tokens}
    event = hooks.Normalizer().normalize('post_api_request', payload(provider='Test', usage=values), scope)
    with store.transaction() as connection:
        admin.save_price(connection, ADMIN, price(valid_to='2026-10-31'))
        assert events.ingest_model(connection, event)
        assert not events.ingest_model(connection, event)
    window = schemas.Window('2026-10-01', '2026-11-01', 'Asia/Shanghai')
    with store.read() as connection:
        row = connection.execute('SELECT * FROM llm_requests').fetchone()
        assert row['cached_input_tokens'] == 0
        assert row['input_total_tokens'] == row['uncached_input_tokens'] == input_tokens
        assert row['output_tokens'] == output_tokens
        assert row['total_tokens'] == input_tokens + output_tokens
        assert row['cost_micro_usd'] == input_tokens * 2 + output_tokens * 4
        assert row['cost_source'] == 'estimated'
        result = quality.details(connection, window, ADMIN)['window']
        assert result['requests'] == 1
        assert result['missing_usage'] == result['missing_cache'] == result['unknown_cost'] == 0


@pytest.mark.parametrize('usage', [
    {'input_tokens': 0, 'cache_read_tokens': None, 'cache_write_tokens': 0, 'prompt_tokens': 0, 'output_tokens': 0},
    {'input_tokens': 0, 'cache_read_tokens': 0, 'cache_write_tokens': 0, 'output_tokens': 0},
    {'input_tokens': 0, 'cache_read_tokens': False, 'cache_write_tokens': 0, 'prompt_tokens': 0, 'output_tokens': 0},
])
def test_missing_or_invalid_zero_fields_remain_unknown(scope, usage):
    event = hooks.Normalizer().normalize('post_api_request', payload(usage=usage), scope)
    assert event.input_total_tokens is event.cached_input_tokens is event.output_tokens is None
    assert event.pricing_supported is False


def test_context_does_not_cross_turn_or_profile_and_is_bounded(scope):
    normalizer = hooks.Normalizer(capacity=2)
    normalizer.normalize('pre_llm_call', payload(sender_id='ou-test'), scope)
    assert normalizer.normalize('post_api_request', payload(turn_id='other-turn'), scope).external_user_id is None
    other = hooks.HookContext('i1', 'p2', scope.db_path)
    assert normalizer.normalize('post_api_request', payload(), other).external_user_id is None
    for index in range(8):
        normalizer.normalize('pre_llm_call', payload(turn_id=str(index), sender_id='ou-test'), scope)
    assert len(normalizer.identities) == 2
    normalizer.normalize('on_session_end', payload(turn_id='7'), scope)
    assert len(normalizer.identities) == 1


def test_missing_stable_keys_and_times_are_rejected(scope):
    normalizer = hooks.Normalizer()
    for fields in [{'api_request_id': ''}, {'session_id': ''}, {'started_at': None}, {'ended_at': 0}, {'provider': 'https://token@host'}]:
        with pytest.raises(ValueError):
            normalizer.normalize('post_api_request', payload(**fields), scope)
    with pytest.raises(ValueError):
        normalizer.normalize('post_tool_call', payload(tool_call_id='', tool_name='terminal', status='ok'), scope)


def test_auxiliary_failure_is_not_success_and_stream_usage_is_unknown(scope):
    normalizer = hooks.Normalizer()
    failed = normalizer.normalize('post_auxiliary_call', payload(error_type='TimeoutError', error='SECRET'), scope)
    assert failed.status == 'failed' and failed.request_kind == 'auxiliary'
    assert failed.output_tokens is None
    streaming = normalizer.normalize('post_auxiliary_call', payload(streaming=True, usage=None), scope)
    assert streaming.request_kind == 'auxiliary' and streaming.input_total_tokens is None


def test_tool_classification_uses_actual_registry_not_name_prefix(monkeypatch, scope):
    mapping = {'terminal': 'terminal', 'mcp__fake__tool': None, 'search-a': 'mcp-catalog', 'search-b': 'mcp-other'}
    registry = SimpleNamespace(get_toolset_for_tool=lambda name: mapping.get(name))
    monkeypatch.setitem(sys.modules, 'tools.registry', SimpleNamespace(registry=registry))
    assert collector_module.classify_tool('mcp__fake__tool') == ('unknown', None)
    assert collector_module.classify_tool('terminal') == ('local', None)
    normalizer = hooks.Normalizer(collector_module.classify_tool)
    event = normalizer.normalize('post_tool_call', payload(tool_name='search-a', tool_call_id='call-a', status='error', args={'key': 'SECRET'}, result='DO_NOT_STORE', duration_ms=12), scope)
    assert event.tool_type == 'mcp' and event.mcp_server_id == 'catalog' and event.status == 'failed'
    assert 'SECRET' not in event.model_dump_json() and 'DO_NOT_STORE' not in event.model_dump_json()
    reused_id = normalizer.normalize('post_tool_call', payload(turn_id='other', tool_name='search-a', tool_call_id='call-a', status='error'), scope)
    assert reused_id.source_event_id != event.source_event_id


def test_bounded_buffer_drops_are_observable_without_hook_blocking(scope):
    worker = collector_module.Collector(scope.db_path, capacity=1, start=False)
    event = hooks.Normalizer().normalize('post_api_request', payload(), scope)
    started = time.monotonic()
    for _ in range(10):
        worker.submit(scope, event)
    assert time.monotonic() - started < 0.5
    assert worker.buffer.qsize() == 1
    assert worker.snapshot()[0][1]['counters']['dropped'] == 9
    worker.tick()
    with worker.store.read() as connection:
        assert quality.collection(connection)['status'] == 'degraded'
        assert connection.execute('SELECT total_tokens FROM llm_requests').fetchone()[0] == 120


def test_durable_queue_restart_replay_and_poison_quarantine(scope):
    worker = collector_module.Collector(scope.db_path, start=False)
    worker.store = db.Store(scope.db_path)
    event = hooks.Normalizer().normalize('post_api_request', payload(), scope)
    worker.note(scope)
    worker.persist(scope, event)
    restarted = collector_module.Collector(scope.db_path, start=False)
    restarted.store = db.Store(scope.db_path)
    assert restarted.drain() == 1
    for _ in range(3):
        restarted.persist(scope, event)
        restarted.drain()
    with restarted.store.transaction() as connection:
        connection.execute("INSERT INTO collection_queue(event_key,kind,payload_json,received_at) VALUES('poison','model','{}','now')")
    restarted.drain()
    with restarted.store.read() as connection:
        assert connection.execute('SELECT count(*) FROM llm_requests').fetchone()[0] == 1
        poison = connection.execute("SELECT * FROM collection_queue WHERE event_key='poison'").fetchone()
        assert poison['status'] == 'failed' and poison['attempts'] == 3
        assert poison['payload_json'] is None


def test_concurrent_producers_and_two_workers_share_database_safely(scope):
    first = collector_module.Collector(scope.db_path, start=False)
    second = collector_module.Collector(scope.db_path, start=False)
    first.store = db.Store(scope.db_path)
    second.store = db.Store(scope.db_path)
    normalizer = hooks.Normalizer()
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda index: first.submit(scope, normalizer.normalize('post_api_request', payload(api_request_id=f'api-{index}'), scope)), range(80)))
    while not first.buffer.empty():
        context, event, _ = first.buffer.get_nowait()
        first.persist(context, event)
        first.buffer.task_done()
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda worker: worker.drain(), [first, second]))
    with first.store.read() as connection:
        assert connection.execute('SELECT count(*) FROM llm_requests').fetchone()[0] == 80
        assert connection.execute("SELECT count(*) FROM event_inbox WHERE status='done'").fetchone()[0] == 80


def test_dispatcher_disabled_or_broken_context_never_throws(scope, monkeypatch, caplog):
    disabled = collector_module.Dispatcher(context_factory=lambda: (_ for _ in ()).throw(RuntimeError('SECRET')), enabled=False)
    assert disabled.callback('post_api_request', **payload()) is None
    assert not disabled.collectors
    broken = collector_module.Dispatcher(context_factory=lambda: (_ for _ in ()).throw(RuntimeError('SECRET')), enabled=True)
    assert broken.callback('post_api_request', **payload()) is None
    assert broken.failures == {'context_unavailable': 1}
    assert 'SECRET' not in caplog.text
    dispatcher = collector_module.Dispatcher(context_factory=lambda: scope, enabled=True)
    assert dispatcher.callback('post_api_request', **payload()) is None
    dispatcher.close()
    store = db.Store(scope.db_path)
    with store.read() as connection:
        assert connection.execute('SELECT count(*) FROM llm_requests').fetchone()[0] == 1


def test_context_resolves_active_profile_for_each_call(tmp_path, monkeypatch):
    current = [tmp_path / 'profile-a']
    monkeypatch.setitem(sys.modules, 'hermes_constants', SimpleNamespace(get_hermes_home=lambda: current[0], profile_name_for_home=lambda path: path.name))
    monkeypatch.delenv('USAGE_MANAGER_DB_PATH', raising=False)
    monkeypatch.delenv('USAGE_MANAGER_PROFILE_ID', raising=False)
    first = collector_module.context()
    current[0] = tmp_path / 'profile-b'
    second = collector_module.context()
    assert first.profile_id == 'profile-a' and second.profile_id == 'profile-b'
    assert first.db_path != second.db_path and first.instance_id == second.instance_id
    monkeypatch.setenv('USAGE_MANAGER_DB_PATH', str(tmp_path / 'shared.sqlite3'))
    assert collector_module.context().db_path == str(tmp_path / 'shared.sqlite3')


def test_quality_reports_missing_fields_scoped_and_pending_backlog(scope):
    worker = collector_module.Collector(scope.db_path, start=False)
    worker.submit(scope, hooks.Normalizer().normalize('post_api_request', payload(usage=None), scope))
    worker.tick()
    with worker.store.read() as connection:
        result = quality.details(connection, importlib.import_module(api.__package__ + '.schemas').Window('2026-10-01', '2026-11-01', 'Asia/Shanghai'), ADMIN)
    assert result['window']['missing_usage'] == 1 and result['window']['missing_usage_rate'] == 1
    assert result['collection']['status'] == 'observed'
    assert result['collection']['hermes_runtime'] == 'unverified'


def test_session_content_opt_in_allowlist_read_only_pagination_and_redaction(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    (home / 'state.db').touch()
    calls = []
    class SessionDB:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def get_session(self, session_id):
            return {'id': session_id, 'profile_name': 'p1'}
        def get_messages(self, session_id, limit=None, offset=0, latest=False, include_ancestors=False):
            calls.append({'limit': limit, 'offset': offset, 'latest': latest, 'include_ancestors': include_ancestors})
            return [{'id': index, 'role': 'user' if index == 0 else 'tool', 'timestamp': 0, 'content': 'api_key=SECRET password=SECRET sk-test123456789', 'is_error': True} for index in range(3)]
        def close(self):
            calls.append('closed')
    provider = content.HermesSessionContentProvider(SessionDB, {'i1/p1': str(home)})
    with pytest.raises(Exception) as disabled:
        provider.read('i1', 'p1', 's1')
    assert disabled.value.status_code == 503 and calls == []
    monkeypatch.setenv('USAGE_MANAGER_SESSION_CONTENT', '1')
    result = provider.read('i1', 'p1', 's1', 0, 2)
    assert calls[0]['read_only'] is True and calls[-1] == 'closed'
    assert calls[1]['include_ancestors'] is False and calls[1]['limit'] == 3
    assert result['pagination']['has_more'] is True
    assert 'SECRET' not in json.dumps(result) and 'sk-test123456789' not in json.dumps(result)
    assert result['messages'][-1]['tools'][0]['result'] == '[工具结果已隐藏]'
    assert result['messages'][0]['time'] == '1970-01-01T00:00:00+00:00'
    assert result['messages'][-1]['tools'][0]['time'] == '1970-01-01T00:00:00+00:00'
    with pytest.raises(Exception) as denied:
        provider.read('other-instance', 'p1', 's1')
    assert denied.value.status_code == 503


def test_timeline_auditor_cannot_read_body_and_failure_is_audited(scope):
    runtime = api.Runtime(db.Store(scope.db_path), content_provider=content.HermesSessionContentProvider())
    insert(runtime, model())
    app = FastAPI()
    app.dependency_overrides[api.get_runtime] = lambda: runtime
    principal = importlib.import_module(api.__package__ + '.security').Principal
    app.dependency_overrides[api.get_principal] = lambda: principal('auditor', 'auditor')
    app.include_router(api.router, prefix=PREFIX)
    client = TestClient(app)
    session_id = events.key('i1', 'p1', 's1')
    assert client.get(PREFIX + f'/sessions/{session_id}/timeline', params=RANGE).status_code == 403
    assert client.get(PREFIX + f'/sessions/{session_id}', params=RANGE).status_code == 200
    with runtime.store.read() as connection:
        assert connection.execute("SELECT result FROM audit_access_logs WHERE action='sessions.timeline'").fetchone()[0] == 'denied'


def test_redaction_handles_headers_private_keys_and_nontext():
    text = 'Authorization: Bearer SUPERSECRET\ncookie=sessionSECRET\n-----BEGIN PRIVATE KEY-----\nPRIVATESECRET\n-----END PRIVATE KEY-----'
    clean = content.redact(text)
    assert all(secret not in clean for secret in ['SUPERSECRET', 'sessionSECRET', 'PRIVATESECRET'])
    assert content.redact({'image': 'private'}) == '[非文本内容已隐藏]'


def test_mock_runtime_initialization_is_single_flight(monkeypatch):
    from dev import sqlite_api
    calls = []
    sentinel = object()
    def slow_runtime(path):
        calls.append(path)
        time.sleep(0.03)
        return sentinel
    monkeypatch.setenv('HUM_MOCK_TESTING', '1')
    monkeypatch.setattr(sqlite_api, 'mock_runtime', slow_runtime)
    request = SimpleNamespace(headers={'x-hum-test-case': 'single-flight-unit-case'})
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda index: sqlite_api.selected_runtime(request), range(8)))
    assert results == [sentinel] * 8
    assert len(calls) == 1
    sqlite_api.test_runtime.cache_clear()


def test_pending_backlog_retries_after_write_lock_is_released(scope):
    worker = collector_module.Collector(scope.db_path, start=False)
    worker.store = db.Store(scope.db_path)
    worker.note(scope)
    worker.persist(scope, hooks.Normalizer().normalize('post_api_request', payload(), scope))
    original = worker.store.connect
    def short_wait():
        connection = original()
        connection.execute('PRAGMA busy_timeout=30')
        return connection
    worker.store.connect = short_wait
    with worker.store.transaction():
        with pytest.raises(sqlite3.OperationalError):
            worker.drain()
    with worker.store.read() as connection:
        assert connection.execute("SELECT attempts FROM collection_queue WHERE status='pending'").fetchone()[0] == 0
    assert worker.drain() == 1


def test_same_event_across_profile_workers_is_not_merged(scope):
    worker = collector_module.Collector(scope.db_path, start=False)
    other = hooks.HookContext(scope.instance_id, 'p2', scope.db_path)
    normalizer = hooks.Normalizer()
    for context in (scope, other):
        for _ in range(3):
            worker.submit(context, normalizer.normalize('post_api_request', payload(), context))
    worker.tick()
    with worker.store.read() as connection:
        assert connection.execute('SELECT count(*) FROM sessions').fetchone()[0] == 2
        assert connection.execute('SELECT count(*) FROM llm_requests').fetchone()[0] == 2
        assert quality.collection(connection)['profile_connected'] == 2


def test_secret_redaction_survives_truncation_and_quoted_cookie_values():
    secret = '-----BEGIN PRIVATE KEY-----' + 'A' * 12000 + '-----END PRIVATE KEY-----'
    assert 'AAAA' not in content.redact(secret)
    assert 'SECRET' not in content.redact('cookie="session=SECRET; csrf=SECRET"')
    assert 'SECRET' not in content.redact('Cookie: session=SECRET; csrf=SECRET')


def test_session_reader_rejects_unsupported_signature_and_wrong_owner(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    (home / 'state.db').touch()
    monkeypatch.setenv('USAGE_MANAGER_SESSION_CONTENT', '1')
    class OldSessionDB:
        def __init__(self):
            pass
    provider = content.HermesSessionContentProvider(OldSessionDB, {'i1/p1': str(home)})
    with pytest.raises(Exception) as error:
        provider.read('i1', 'p1', 's1')
    assert error.value.status_code == 503
    closed = []
    class WrongOwner:
        def __init__(self, **kwargs):
            pass
        def get_session(self, session_id):
            return {'profile_name': 'other'}
        def close(self):
            closed.append(True)
    provider = content.HermesSessionContentProvider(WrongOwner, {'i1/p1': str(home)})
    with pytest.raises(Exception) as error:
        provider.read('i1', 'p1', 's1')
    assert error.value.status_code == 503 and closed == [True]


def test_target_entry_callbacks_replay_command_is_mock_only(tmp_path):
    import subprocess
    result = subprocess.run([sys.executable, 'scripts/replay_hooks.py', '--db', str(tmp_path / 'replay.sqlite3')], check=True, capture_output=True, text=True)
    assert 'source=mock; registered_hooks=5; repetitions=3; model_requests=2; mcp_calls=1' in result.stdout
    with pytest.raises(ValueError, match='mode mismatch'):
        db.Store(tmp_path / 'replay.sqlite3', 'live')


def test_expected_profile_inventory_distinguishes_two_of_five(scope, monkeypatch):
    monkeypatch.setenv('USAGE_MANAGER_EXPECTED_PROFILES', json.dumps(['p1', 'p2', 'p3', 'p4', 'p5']))
    worker = collector_module.Collector(scope.db_path, start=False)
    worker.note(scope)
    worker.note(hooks.HookContext(scope.instance_id, 'p2', scope.db_path))
    worker.tick()
    with worker.store.read() as connection:
        state = quality.collection(connection)
    assert state['profile_configured'] == 5 and state['profile_connected'] == 2
    assert state['profile_missing_heartbeat'] == 3
    assert set(state['registered_hooks']) == set(hooks.HOOKS)


def test_registered_callbacks_ignore_future_name_fields(scope, monkeypatch):
    dispatcher = collector_module.Dispatcher(context_factory=lambda: scope, enabled=True)
    monkeypatch.setattr(collector_module, 'dispatcher', dispatcher)
    callbacks = {}
    context = SimpleNamespace(register_hook=lambda name, callback: callbacks.update({name: callback}))
    collector_module.register(context)
    assert callbacks['post_api_request'](**payload(name='future-field', _hook='future-field')) is None
    dispatcher.close()
    with db.Store(scope.db_path).read() as connection:
        assert connection.execute('SELECT count(*) FROM llm_requests').fetchone()[0] == 1


def test_upgrade_m2_database_preserves_existing_facts(tmp_path, monkeypatch):
    import shutil
    migration_root = tmp_path / 'm2-package'
    (migration_root / 'migrations').mkdir(parents=True)
    module_path = Path(db.__file__)
    for migration in (module_path.parent / 'migrations').glob('000[1-4]_*.sql'):
        shutil.copyfile(migration, migration_root / 'migrations' / migration.name)
    path = tmp_path / 'persistent.sqlite3'
    with monkeypatch.context() as patch:
        patch.setattr(db, '__file__', str(migration_root / 'db.py'))
        old = db.Store(path)
        with old.transaction() as connection:
            connection.execute("INSERT INTO departments(id,name) VALUES('existing','Keep')")
            connection.execute("INSERT INTO sessions(session_key,instance_id,profile_id,source_session_id,started_at,last_at) VALUES('old-session','i1','p1','s1','2026-10-15','2026-10-15')")
            connection.execute("INSERT INTO llm_requests(event_key,instance_id,profile_id,source_event_id,session_key,api_request_id,provider,model,occurred_at,status,cost_micro_usd,cost_source) VALUES('old-event','i1','p1','old-request','old-session','api-1','fixture','model','2026-10-15','success',235,'estimated')")
            assert connection.execute('SELECT count(*) FROM schema_migrations').fetchone()[0] == 4
    upgraded = db.Store(path)
    with upgraded.read() as connection:
        assert connection.execute('SELECT name FROM departments').fetchone()[0] == 'Keep'
        assert connection.execute('SELECT count(*) FROM schema_migrations').fetchone()[0] == 5
        assert connection.execute('SELECT count(*) FROM collection_queue').fetchone()[0] == 0
        assert connection.execute('SELECT cost_micro_usd FROM llm_requests').fetchone()[0] == 235


def test_aggregate_moa_summary_is_not_counted_as_an_extra_physical_attempt(scope):
    with pytest.raises(ValueError, match='AGGREGATE'):
        hooks.Normalizer().normalize('post_api_request', payload(moa_references=[]), scope)
