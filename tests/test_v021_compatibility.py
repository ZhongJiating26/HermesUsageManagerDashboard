import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from dashboard.plugin_api import api

collector = importlib.import_module(api.__package__ + '.collector')
hooks = importlib.import_module(api.__package__ + '.adapters.hooks')
content = importlib.import_module(api.__package__ + '.adapters.session_content')
quality = importlib.import_module(api.__package__ + '.quality')
db = importlib.import_module(api.__package__ + '.db')


def test_v021_declared_and_registered_hooks_match_without_missing_auxiliary():
    import yaml
    root = Path(__file__).resolve().parents[1]
    manifest = yaml.safe_load((root / 'plugin.yaml').read_text(encoding='utf-8'))
    # Released installers may cap at v1 even when their runtime accepts v2.
    assert manifest.get('manifest_version', 1) <= 1
    valid = {'pre_llm_call', 'post_api_request', 'api_request_error', 'post_tool_call', 'on_session_end'}
    registered = []
    def register_hook(name, callback):
        assert name in valid
        registered.append(name)
    collector.register(SimpleNamespace(register_hook=register_hook))
    assert set(manifest['provides_hooks']) == set(registered) == valid
    assert 'post_auxiliary_call' not in registered


def test_missing_auxiliary_is_reported_as_partial_not_zero(tmp_path):
    store = db.Store(tmp_path / 'usage.sqlite3')
    with store.read() as connection:
        result = quality.collection(connection)
    assert result['hook_coverage'] == 'partial'
    assert result['unavailable_hooks'] == ['post_auxiliary_call']
    assert result['hermes_runtime'] == 'unverified'


@pytest.mark.parametrize('newer', [False, True])
def test_session_reader_negotiates_explicit_v021_and_newer_signatures(tmp_path, monkeypatch, newer):
    home = tmp_path / 'home'
    home.mkdir()
    (home / 'state.db').touch()
    calls = []
    class SessionDB:
        def __init__(self, db_path=None, read_only=False):
            assert read_only is True
        def get_session(self, session_id):
            return {'profile_name': 'p1'}
        def get_messages(self, session_id, include_inactive=False, include_compacted=False, limit=None, offset=0, latest=False, after_id=None):
            calls.append((limit, offset, latest))
            return [{'id': 1, 'session_id': session_id, 'role': 'user', 'content': 'Allowed'}]
        def close(self):
            calls.append('closed')
    if newer:
        def get_messages(self, session_id, limit=None, offset=0, latest=False, include_ancestors=True):
            assert include_ancestors is False
            calls.append((limit, offset, latest))
            return [{'id': 1, 'role': 'user', 'content': 'Allowed'}]
        SessionDB.get_messages = get_messages
    monkeypatch.setenv('USAGE_MANAGER_SESSION_CONTENT', '1')
    provider = content.HermesSessionContentProvider(SessionDB, {'i1/p1': str(home)})
    result = provider.read('i1', 'p1', 's1', offset=20, limit=10)
    assert calls == [(11, 20, False), 'closed']
    assert result['messages'][0]['text'] == 'Allowed'


def test_unbounded_session_method_is_rejected_without_invocation(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    (home / 'state.db').touch()
    called = []
    class SessionDB:
        def __init__(self, **kwargs):
            pass
        def get_session(self, session_id):
            return {}
        def get_messages(self, session_id):
            called.append('unsafe')
            return []
        def close(self):
            called.append('closed')
    monkeypatch.setenv('USAGE_MANAGER_SESSION_CONTENT', '1')
    with pytest.raises(Exception) as error:
        content.HermesSessionContentProvider(SessionDB, {'i1/p1': str(home)}).read('i1', 'p1', 's1')
    assert error.value.status_code == 503 and called == ['closed']


@pytest.mark.parametrize('mapping,allowed', [
    ('{"i1/home-hash":"default"}', True),
    ('{}', False),
    ('{"i1/home-hash":"other"}', False),
    ('{"i1/home-hash":""}', False),
    ('{"i1/home-hash":null}', False),
    ('[]', False),
    ('invalid-json', False),
    ('{"other/home-hash":"default"}', False),
])
def test_explicit_host_profile_alias_preserves_ownership_check(tmp_path, monkeypatch, mapping, allowed):
    home = tmp_path / 'home'
    home.mkdir()
    (home / 'state.db').touch()
    calls = []
    class SessionDB:
        def __init__(self, db_path=None, read_only=False):
            assert db_path == home / 'state.db' and read_only is True
        def get_session(self, session_id):
            return {'profile_name': 'default', 'title': 'Test api_key=SECRET'}
        def get_messages(self, session_id, limit=None, offset=0, latest=False):
            calls.append('read')
            assert (limit, offset, latest) == (101, 0, False)
            return [{'id': 1, 'session_id': session_id, 'role': 'user', 'content': 'Test'}]
        def close(self):
            calls.append('closed')
    monkeypatch.setenv('USAGE_MANAGER_SESSION_CONTENT', '1')
    monkeypatch.setenv('USAGE_MANAGER_SESSION_PROFILES', mapping)
    provider = content.HermesSessionContentProvider(SessionDB, {'i1/home-hash': str(home)})
    if allowed:
        result = provider.read('i1', 'home-hash', 's1')
        assert result['messages'][0]['text'] == 'Test'
        assert result['title'] == 'Test api_key=[已脱敏]'
        assert calls == ['read', 'closed']
    else:
        with pytest.raises(Exception) as error:
            provider.read('i1', 'home-hash', 's1')
        assert error.value.status_code == 503
        assert 'read' not in calls


@pytest.mark.parametrize('value,expected', [
    (0, '1970-01-01T00:00:00+00:00'),
    ('2026-10-16T08:22:27+08:00', '2026-10-16T00:22:27+00:00'),
    (None, None), (True, None), (float('nan'), None),
    ('2026-10-16T08:22:27', None), ('bad', None), (1e100, None),
])
def test_message_time_never_fabricates_missing_or_invalid_timestamp(value, expected):
    assert content.message_time(value) == expected
