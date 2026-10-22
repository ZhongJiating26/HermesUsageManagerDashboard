import hashlib
import importlib
import json
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from tests.test_m2_sqlite import PREFIX, RANGE, api, client, events, insert, model, runtime

people = importlib.import_module(api.__package__ + '.people')
adapter = importlib.import_module(api.__package__ + '.adapters.people')


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / 'hermes-home'
    home.mkdir()
    monkeypatch.setitem(sys.modules, 'hermes_constants', SimpleNamespace(get_hermes_home=lambda: home, profile_name_for_home=lambda value: 'default'))
    monkeypatch.setenv('USAGE_MANAGER_INSTANCE_ID', 'i1')
    return home


def core(home):
    with sqlite3.connect(home / 'state.db') as c:
        c.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,source,user_id,profile_name,chat_type,parent_session_id,origin_json)')
        for sid, platform, external, profile, kind, parent, name in [
            ('dm-a', 'feishu', 'a', 'default', 'dm', None, '甲'),
            ('dm-b', 'feishu', 'b', 'default', 'dm', None, '乙'),
            ('other-platform', 'lightclawbot', 'a', 'default', 'dm', None, None),
            ('group', 'feishu', 'a', 'default', 'group', None, '甲'),
            ('child', 'subagent', None, 'default', None, 'dm-a', None),
            ('other-profile', 'feishu', 'foreign', 'other', 'dm', None, '不可见'),
        ]:
            c.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)', (sid, platform, external, profile, kind, parent, json.dumps({'platform': platform, 'user_id': external, 'user_name': name, 'chat_type': kind})))
    return home / 'state.db'


def legacy(runtime, identifier, session, **kwargs):
    insert(runtime, model(identifier, session_id=session, profile_id='default', user_id='legacy-placeholder', **kwargs))
    with runtime.store.transaction() as c:
        c.execute("UPDATE llm_requests SET user_id=NULL,identity_status='unresolved' WHERE source_event_id=?", (identifier,))
        c.execute('UPDATE sessions SET user_id=NULL')


def test_discovery_backfills_only_verified_private_or_explicit_turn_identities(runtime, home):
    legacy(runtime, 'dm', 'dm-a')
    legacy(runtime, 'child', 'child')
    legacy(runtime, 'group-unknown', 'group')
    legacy(runtime, 'group-explicit', 'group', external_user_id='b', platform='feishu')
    legacy(runtime, 'foreign-instance', 'dm-a', instance_id='i2')
    legacy(runtime, 'foreign-profile', 'other-profile', platform='feishu')
    with runtime.store.transaction() as c:
        events.ingest_tool(c, events.ToolEvent(instance_id='i1', profile_id='default', source_event_id='tool', session_id='dm-a', user_id='legacy-placeholder', tool_id='tool', tool_name='tool', occurred_at='2026-10-15T00:00:00+08:00'))
        c.execute("UPDATE tool_calls SET user_id=NULL,identity_status='unresolved'")
        c.execute('UPDATE sessions SET user_id=NULL')
    path = core(home)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    report = people.sync(runtime.store, home=home, profile_name='default', instance_id='i1')
    assert (report['created'], report['requests'], report['tools']) == (3, 3, 1)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    with runtime.store.read() as c:
        users = {(r['platform'], r['external_id']): dict(r) for r in c.execute('SELECT * FROM users')}
        assert len(users) == 3
        assert all(r['department_id'] is None for r in users.values())
        requests = {r['source_event_id']: dict(r) for r in c.execute('SELECT * FROM llm_requests')}
        assert requests['dm']['user_id'] == users['feishu', 'a']['id']
        assert requests['child']['user_id'] == users['feishu', 'a']['id']
        assert requests['group-explicit']['user_id'] == users['feishu', 'b']['id']
        for key in ('group-unknown', 'foreign-instance', 'foreign-profile'):
            assert requests[key]['user_id'] is None
        assert c.execute('SELECT user_id FROM tool_calls').fetchone()[0] == users['feishu', 'a']['id']
    again = people.sync(runtime.store, home=home, profile_name='default', instance_id='i1')
    assert [again[k] for k in ('created', 'requests', 'tools', 'sessions')] == [0, 0, 0, 0]


def test_new_events_auto_create_accounts_and_dm_fallback_but_never_group_owner(runtime, home):
    core(home)
    insert(runtime, model('dm', session_id='dm-a', profile_id='default'))
    insert(runtime, model('group-unknown', session_id='group', profile_id='default'))
    insert(runtime, model('group-turn', session_id='group', profile_id='default', platform='feishu', external_user_id='b'))
    insert(runtime, model('cross-profile', session_id='dm-a', profile_id='other'))
    with runtime.store.read() as c:
        rows = {r['source_event_id']: dict(r) for r in c.execute('SELECT * FROM llm_requests')}
        assert rows['dm']['user_id'] is not None
        assert rows['dm']['identity_source'] == 'session_dm'
        assert rows['group-turn']['user_id'] is not None
        assert rows['group-turn']['user_id'] != rows['dm']['user_id']
        assert rows['group-turn']['external_user_id'] == 'b'
        assert rows['group-unknown']['user_id'] is None
        assert rows['cross-profile']['user_id'] is None


def test_manual_names_disabled_accounts_existing_identity_and_past_department_preserved(runtime, client, home):
    path = core(home)
    people.sync(runtime.store, home=home, profile_name='default', instance_id='i1')
    with runtime.store.transaction() as c:
        uid = c.execute("SELECT id FROM users WHERE platform='feishu' AND external_id='a'").fetchone()[0]
        c.execute("INSERT INTO departments(id,name) VALUES('dept','当前部门')")
        c.execute("UPDATE users SET status='inactive' WHERE external_id='b'")
    response = client.patch(PREFIX + '/people/users/' + uid, json={'name': '管理员姓名', 'external_id': 'a', 'platform': 'feishu', 'profile': '', 'department_id': 'dept'})
    assert response.status_code == 200
    insert(runtime, model('old', session_id='dm-a', profile_id='default'))
    insert(runtime, model('disabled', session_id='dm-b', profile_id='default'))
    with runtime.store.transaction() as c:
        c.execute("UPDATE llm_requests SET user_id=NULL,identity_status='unresolved' WHERE source_event_id='old'")
        c.execute("UPDATE users SET name='临时名',name_source='identifier' WHERE platform='lightclawbot'")
    people.sync(runtime.store, home=home, profile_name='default', instance_id='i1')
    with runtime.store.read() as c:
        assert c.execute('SELECT name FROM users WHERE id=?', (uid,)).fetchone()[0] == '管理员姓名'
        row = c.execute("SELECT * FROM llm_requests WHERE source_event_id='old'").fetchone()
        assert row['user_id'] == uid and row['department_id'] is None
        assert c.execute("SELECT user_id FROM llm_requests WHERE source_event_id='disabled'").fetchone()[0] is None
    # Core DB remains byte-for-byte unchanged through all sync/ingestion operations.
    assert path.exists()


def test_sync_api_admin_only_and_mock_never_reads_home(runtime, client, home, monkeypatch):
    core(home)
    for role in ('user', 'department', 'auditor'):
        assert client.post(PREFIX + '/people/sync', headers={'test-role': role}).status_code == 403
    response = client.post(PREFIX + '/people/sync')
    assert response.status_code == 200 and response.json()['data']['created'] == 3
    users = client.get(PREFIX + '/people/users').json()['data']
    assert len(users) == 3 and all(row['department_id'] == '' for row in users)
    with runtime.store.read() as c:
        assert c.execute("SELECT count(*) FROM audit_access_logs WHERE action='people.sync' AND actor_id='test-admin'").fetchone()[0] == 1
    runtime.store.source = 'mock'
    monkeypatch.setattr(people, 'metadata', lambda **kwargs: pytest.fail('Mock must never inspect real metadata'))
    assert people.sync(runtime.store)['available'] is False


def test_unavailable_or_conflicting_session_metadata_is_not_guessed(runtime, home):
    assert people.sync(runtime.store, home=home, profile_name='default')['available'] is False
    core(home)
    with sqlite3.connect(home / 'state.db') as c:
        c.execute("UPDATE sessions SET origin_json=? WHERE id='dm-a'", (json.dumps({'platform': 'feishu', 'user_id': 'different', 'user_name': '错误姓名', 'chat_type': 'dm'}),))
    data = adapter.metadata(home=home, profile_name='default')
    assert adapter.owner(data['sessions'], 'dm-a') is None
    assert adapter.owner(data['sessions'], 'child') is None
    insert(runtime, model('conflict', session_id='dm-a', profile_id='default'))
    with runtime.store.read() as c:
        assert c.execute('SELECT user_id FROM llm_requests').fetchone()[0] is None


def test_verified_legacy_home_profile_is_scoped_to_this_home(runtime, home):
    legacy_profile = 'home-' + events.key(str(home))[:20]
    insert(runtime, model('old-home', session_id='dm-a', profile_id=legacy_profile))
    core(home)
    result = people.sync(runtime.store, home=home, profile_name='default', instance_id='i1')
    assert result['requests'] == 1
    insert(runtime, model('new-home', session_id='dm-b', profile_id=legacy_profile))
    with runtime.store.read() as c:
        assert c.execute('SELECT count(*) FROM llm_requests WHERE user_id IS NOT NULL').fetchone()[0] == 2
