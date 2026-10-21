import json
import secrets
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import collector
from backend.adapters.session_content import HermesSessionContentProvider
from backend.events import ModelEvent, ingest_model, key
from backend.standalone import create_app, initialize_auth


@pytest.fixture
def local_sessions(tmp_path, monkeypatch):
    home = tmp_path / 'user' / '.hermes'
    home.mkdir(parents=True)
    (home / 'state.db').touch()
    monkeypatch.setattr(Path, 'home', lambda: home.parent)
    monkeypatch.setitem(sys.modules, 'hermes_constants', SimpleNamespace(get_hermes_home=lambda: home))
    for name in ('USAGE_MANAGER_SESSION_CONTENT', 'USAGE_MANAGER_SESSION_HOMES', 'USAGE_MANAGER_SESSION_PROFILES', 'USAGE_MANAGER_TOOL_CONTENT', 'USAGE_MANAGER_PROFILE_ID'):
        monkeypatch.delenv(name, raising=False)
    calls = []

    class SessionDB:
        def __init__(self, db_path=None, read_only=False):
            assert db_path == home / 'state.db' and read_only is True
            calls.append('open')

        def get_session(self, session_id):
            return {'profile_name': 'default', 'title': 'Readable conversation'}

        def get_messages(self, session_id, limit=None, offset=0, latest=False):
            assert limit == 101 and offset == 0 and latest is False
            return [
                {'id': 1, 'session_id': session_id, 'role': 'user', 'content': 'Hello'},
                {'id': 2, 'session_id': session_id, 'role': 'assistant', 'content': 'Welcome', 'tool_calls': [{'id': 'call-1', 'function': {'name': 'tool_call', 'arguments': json.dumps({'query': 'example', 'api_key': 'argument-secret', 'headers': {'Authorization': 'Bearer header-secret'}})}}]},
                {'id': 3, 'session_id': session_id, 'role': 'tool', 'tool_call_id': 'call-1', 'tool_name': 'mcp__catalog__search', 'content': 'Result password=secret-value'},
            ]

        def close(self):
            calls.append('close')

    monkeypatch.setitem(sys.modules, 'hermes_state', SimpleNamespace(SessionDB=SessionDB))
    return home, collector.context(), calls


def test_logged_in_standalone_admin_can_read_local_conversation_without_manual_flags(local_sessions, tmp_path):
    home, scope, calls = local_sessions
    auth = tmp_path / 'credentials/auth.json'
    password = secrets.token_urlsafe(24)
    initialize_auth(auth, password)
    app = create_app(auth, tmp_path / 'usage.sqlite3', 'http://testserver', True)
    runtime = app.state.hum_runtime
    with runtime.store.transaction() as connection:
        ingest_model(connection, ModelEvent(instance_id=scope.instance_id, profile_id=scope.profile_id, source_event_id='one', session_id='s1', api_request_id='one', provider='Test', model='test', occurred_at='2026-10-20T00:00:00+00:00'))
    path = '/api/plugins/hermes-usage-manager/sessions/' + key(scope.instance_id, scope.profile_id, 's1') + '/timeline'
    params = {'from': '2026-10-01', 'to': '2026-11-01'}
    before = (home / 'state.db').read_bytes()
    with TestClient(app) as client:
        assert client.get(path, params=params).status_code == 401
        assert not calls
        assert client.post('/api/auth/login', headers={'Origin': 'http://testserver'}, json={'password': password}).status_code == 200
        response = client.get(path, params=params)
        assert response.status_code == 200, response.text
        result = response.json()['data']
        assert [message['text'] for message in result['messages'][:2]] == ['Hello', 'Welcome']
        assert result['messages'][2]['tools'][0]['result'] == 'Result password=[已脱敏]'
        tool = result['messages'][2]['tools'][0]
        assert tool['name'] == 'mcp__catalog__search'
        assert json.loads(tool['args'])['query'] == 'example'
        assert 'argument-secret' not in tool['args'] and 'header-secret' not in tool['args']
        assert calls == ['open', 'close']
    assert (home / 'state.db').read_bytes() == before
    with runtime.store.read() as connection:
        assert connection.execute("SELECT result FROM audit_access_logs WHERE action='sessions.timeline'").fetchone()[0] == 'ok'


def test_local_admin_does_not_read_another_profile_or_bypass_explicit_disable(local_sessions, monkeypatch):
    _, scope, calls = local_sessions
    provider = HermesSessionContentProvider(local_admin=True)
    with pytest.raises(HTTPException) as error:
        provider.read(scope.instance_id, 'another-profile', 's1')
    assert error.value.status_code == 503
    assert not calls
    monkeypatch.setenv('USAGE_MANAGER_SESSION_CONTENT', '0')
    with pytest.raises(HTTPException):
        provider.read(scope.instance_id, scope.profile_id, 's1')
    assert not calls


def test_native_provider_remains_explicit_and_home_hash_keeps_local_history_readable(local_sessions):
    _, scope, calls = local_sessions
    with pytest.raises(HTTPException):
        HermesSessionContentProvider().read(scope.instance_id, scope.profile_id, 's1')
    assert not calls
    result = HermesSessionContentProvider(local_admin=True).read('previous-instance-label', scope.profile_id, 's1')
    assert result['messages'][0]['text'] == 'Hello'


def test_tool_content_disable_hides_both_arguments_and_results(local_sessions, monkeypatch):
    _, scope, _ = local_sessions
    monkeypatch.setenv('USAGE_MANAGER_TOOL_CONTENT', '0')
    result = HermesSessionContentProvider(local_admin=True).read(scope.instance_id, scope.profile_id, 's1')
    tool = result['messages'][2]['tools'][0]
    assert tool['name'] == 'mcp__catalog__search'
    assert tool['args'] == '[工具参数已隐藏]' and tool['result'] == '[工具结果已隐藏]'


def test_tool_call_linking_across_page_and_reused_ids_is_bounded(local_sessions):
    _, scope, _ = local_sessions
    requests = []
    rows = [
        {'role': 'assistant', 'tool_calls': json.dumps([{'id': 'same', 'function': {'name': 'first', 'arguments': '{"value": 1}'}}])},
        {'role': 'tool', 'tool_call_id': 'same', 'content': 'one'},
        {'role': 'assistant', 'tool_calls': [{'id': 'same', 'function': {'name': 'second', 'arguments': {'value': 2}}}]},
        {'role': 'tool', 'tool_call_id': 'same', 'content': 'two'},
        {'role': 'tool', 'tool_call_id': 'missing', 'tool_name': 'orphan', 'content': 'no call'},
    ]
    class SessionDB:
        def __init__(self, **kwargs):
            assert kwargs['read_only'] is True
        def get_session(self, session_id):
            return {'profile_name': 'default'}
        def get_messages(self, session_id, limit=None, offset=0, latest=False):
            requests.append((offset, limit))
            return rows[offset:offset + limit]
        def close(self):
            pass
    provider = HermesSessionContentProvider(factory=SessionDB, local_admin=True)
    first = provider.read(scope.instance_id, scope.profile_id, 's1', offset=1, limit=1)
    assert first['messages'][0]['tools'][0]['name'] == 'first'
    assert json.loads(first['messages'][0]['tools'][0]['args']) == {'value': 1}
    assert first['pagination'] == {'offset': 1, 'limit': 1, 'has_more': True, 'returned': 1}
    second = provider.read(scope.instance_id, scope.profile_id, 's1', offset=3, limit=2)
    assert [t['name'] for t in second['messages'][0]['tools']] == ['second', 'orphan']
    assert json.loads(second['messages'][0]['tools'][0]['args']) == {'value': 2}
    assert second['messages'][0]['tools'][1]['args'] == '[当前读取范围未找到对应调用参数]'
    assert second['pagination']['has_more'] is False
    provider.read(scope.instance_id, scope.profile_id, 's1', offset=1000, limit=100)
    assert requests[-1] == (800, 301)
