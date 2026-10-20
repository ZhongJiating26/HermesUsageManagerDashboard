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
                {'id': 2, 'session_id': session_id, 'role': 'assistant', 'content': 'Welcome'},
                {'id': 3, 'session_id': session_id, 'role': 'tool', 'content': 'Result password=secret-value'},
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
