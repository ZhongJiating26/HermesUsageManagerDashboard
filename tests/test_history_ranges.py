import hashlib
import importlib
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from backend.adapters.history import user_history
from tests.test_m2_sqlite import PREFIX, RANGE, api, client, db, insert, model, runtime


def test_all_time_includes_old_records_but_preserves_authorization(runtime, client):
    with runtime.store.transaction() as c:
        for i in (1, 2):
            c.execute('INSERT INTO departments(id,name) VALUES(?,?)', (f'd{i}', f'D{i}'))
            c.execute('INSERT INTO users(id,name,external_id,department_id) VALUES(?,?,?,?)', (f'u{i}', f'U{i}', f'e{i}', f'd{i}'))
    insert(runtime, model('old', user_id='u1', department_id='d1', occurred_at='2020-01-01T00:00:00+00:00'))
    insert(runtime, model('new', user_id='u2', department_id='d2'))
    params = RANGE | {'all_time': 'true'}
    assert client.get(PREFIX + '/requests', params=RANGE).json()['meta']['total'] == 1
    response = client.get(PREFIX + '/overview/summary', params=params)
    assert response.status_code == 200
    value = response.json()
    assert value['meta']['all_time'] is True and value['meta']['from'] is None
    assert value['data']['count'] == 2
    assert len(value['data']['trend']) == 82
    assert value['data']['trend'][0]['day'] == '2020-01'
    assert sum(row['total_tokens'] or 0 for row in value['data']['trend']) == 240
    scoped = client.get(PREFIX + '/requests', params=params, headers={'test-role': 'department'}).json()
    assert scoped['meta']['total'] == 1
    assert scoped['data'][0]['department_id'] == 'd1'
    assert client.get(PREFIX + '/requests', params={'from': '2020-01-01', 'to': '2026-10-16'}).status_code == 422


@pytest.fixture
def history_home(tmp_path, runtime):
    home = tmp_path / 'hermes-home'
    home.mkdir()
    with runtime.store.transaction() as c:
        for uid, name, external, department in [('mao', '毛宁', 'open-mao', 'd1'), ('zhong', '钟佳挺', 'open-zhong', 'd2')]:
            c.execute('INSERT INTO departments(id,name) VALUES(?,?)', (department, department))
            c.execute('INSERT INTO users(id,name,platform,external_id,department_id) VALUES(?,?,?,?,?)', (uid, name, 'feishu', external, department))
    with sqlite3.connect(home / 'state.db') as c:
        c.execute('CREATE TABLE sessions(id,source,user_id,parent_session_id,profile_name)')
        c.execute('CREATE TABLE session_model_usage(session_id,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,api_call_count)')
        c.executemany('INSERT INTO sessions VALUES(?,?,?,?,?)', [
            ('s-mao', 'feishu', 'open-mao', None, 'default'),
            ('s-zhong', 'feishu', 'open-zhong', None, 'default'),
            ('child', 'subagent', None, 's-mao', 'default'),
            ('other-profile', 'feishu', 'open-zhong', None, 'other'),
            ('unknown', 'cli', None, None, None),
        ])
        c.executemany('INSERT INTO session_model_usage VALUES(?,?,?,?,?,?)', [
            ('s-mao', 100, 1000000, 0, 100, 5), ('child', 2000000, 0, 10, 0, 7),
            ('s-zhong', 1000000, 0, 0, 20, 9), ('other-profile', 100000000, 0, 0, 0, 10),
            ('unknown', None, None, None, None, 1),
        ])
    return home


def test_history_ranking_uses_aggregate_once_and_keeps_it_outside_requests(runtime, history_home):
    path = history_home / 'state.db'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with runtime.store.read() as c:
        result = user_history(c, home=history_home, profile_name='default')
        assert [r['name'] for r in result['users']] == ['毛宁', '钟佳挺', '未归属']
        assert result['users'][0]['tokens'] == 3000210
        assert result['users'][0]['api_calls'] == 12 and result['users'][0]['sessions'] == 2
        assert result['users'][-1]['tokens'] is None
        assert result['users'][-1]['unknown_rows'] == 1
        assert c.execute('SELECT count(*) FROM llm_requests').fetchone()[0] == 0
        filtered = user_history(c, department_id='d2', home=history_home, profile_name='default')
        assert [r['name'] for r in filtered['users']] == ['钟佳挺']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_admin_history_endpoint_and_scoped_roles(runtime, client, history_home, monkeypatch):
    module = importlib.import_module(api.__package__ + '.adapters.history')
    monkeypatch.setattr(module, 'hermes_home', lambda: history_home)
    monkeypatch.setitem(sys.modules, 'hermes_constants', SimpleNamespace(profile_name_for_home=lambda home: 'default'))
    result = client.get(PREFIX + '/history/users')
    assert result.status_code == 200
    assert result.json()['data']['users'][0]['name'] == '毛宁'
    for role in ('department', 'user', 'auditor'):
        assert client.get(PREFIX + '/history/users', headers={'test-role': role}).status_code == 403
