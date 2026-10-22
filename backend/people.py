"""Discover platform accounts and fill verified missing identities, not departments."""

import hashlib
import json
import os
import socket
import sqlite3
from pathlib import Path

from .adapters.people import metadata, owner, text
from .db import now


def account(connection, platform, external_id, name=None):
    platform, external_id, name = text(platform, 50), text(external_id), text(name, 50)
    if not platform or not external_id or platform in {'unknown', 'cli', 'subagent'}:
        return None, False
    row = connection.execute('SELECT id,status,name_source,name FROM users WHERE platform=? AND external_id=?', (platform, external_id)).fetchone()
    if row:
        if row['status'] != 'active':
            return None, False
        if name and name != external_id and row['name_source'] != 'manual' and row['name'] != name:
            connection.execute("UPDATE users SET name=?,name_source='platform' WHERE id=?", (name, row['id']))
        return row['id'], False
    uid = 'u-' + hashlib.sha256(json.dumps([platform, external_id], ensure_ascii=False).encode()).hexdigest()[:32]
    display = name if name and name != external_id else (platform + ' · ' + external_id)[:50]
    connection.execute('INSERT INTO users(id,name,platform,external_id,name_source) VALUES(?,?,?,?,?)', (uid, display, platform, external_id, 'platform' if name and name != external_id else 'identifier'))
    return uid, True


def department_at(connection, user_id, timestamp):
    row = connection.execute('SELECT department_id FROM department_membership WHERE user_id=? AND valid_from<=? AND (valid_to IS NULL OR valid_to>?) ORDER BY valid_from DESC LIMIT 1', (user_id, timestamp, timestamp)).fetchone()
    return row[0] if row else None


def prepare(connection, event):
    source = connection.execute("SELECT value_json FROM plugin_settings WHERE key='data_source'").fetchone()
    if not source or json.loads(source[0]) != 'live' or event.user_id:
        return event
    if event.external_user_id and event.platform:
        return event.model_copy(update={'identity_source': 'hook'})
    try:
        result = metadata(session_id=event.session_id)
        identity = owner(result['sessions'], event.session_id) if event.profile_id in result.get('aliases', [result['profile']]) else None
    except (OSError, ValueError, sqlite3.Error):
        return event
    if identity:
        return event.model_copy(update={'platform': identity['platform'], 'external_user_id': identity['external_id'],
                                        'external_user_name': identity['name'], 'identity_source': 'session_dm'})
    return event


def sync(store, *, home=None, profile_name=None, instance_id=None, actor=None):
    if store.source != 'live':
        return {'available': False, 'message': '模拟环境不读取真实 Hermes 人员', 'created': 0}
    result = metadata(home=home, profile_name=profile_name)
    if not result['available']:
        return {k: v for k, v in result.items() if k != 'sessions'} | {'created': 0}
    instance_id = instance_id or os.environ.get('USAGE_MANAGER_INSTANCE_ID') or 'instance-' + hashlib.sha256(json.dumps((socket.gethostname(), str(Path.home())), ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()[:24]
    report = {'available': True, 'created': 0, 'requests': 0, 'tools': 0, 'sessions': 0, 'scope': 'current_hermes_home', 'at': now()}
    aliases = result['aliases']
    placeholders = ','.join('?' for _ in aliases)
    with store.transaction() as connection:
        for row in result['sessions'].values():
            if row['platform'] and row['external_id']:
                _, created = account(connection, row['platform'], row['external_id'], row['name'])
                report['created'] += int(created)
        mapping = {(r['platform'], r['external_id']): r['id'] for r in connection.execute("SELECT id,platform,external_id FROM users WHERE status='active'")}
        for table, label in (('llm_requests', 'requests'), ('tool_calls', 'tools')):
            cursor = connection.execute(f'SELECT r.event_key,r.occurred_at,r.identity_platform,r.external_user_id,s.source_session_id FROM {table} r JOIN sessions s USING(session_key) WHERE r.instance_id=? AND r.profile_id IN ({placeholders}) AND r.user_id IS NULL', (instance_id, *aliases))
            while batch := cursor.fetchmany(500):
                for event in batch:
                    identity = owner(result['sessions'], event['source_session_id'])
                    platform, external = event['identity_platform'], event['external_user_id']
                    source = 'hook'
                    if not (platform and external) and identity:
                        platform, external, source = identity['platform'], identity['external_id'], 'session_dm'
                    uid = mapping.get((platform, external))
                    if uid:
                        department = department_at(connection, uid, event['occurred_at'])
                        report[label] += connection.execute(f"UPDATE {table} SET user_id=?,department_id=coalesce(department_id,?),identity_status='resolved',identity_platform=?,external_user_id=?,identity_source=? WHERE event_key=? AND user_id IS NULL", (uid, department, platform, external, source, event['event_key'])).rowcount
        for row in connection.execute(f'SELECT session_key,source_session_id,started_at FROM sessions WHERE instance_id=? AND profile_id IN ({placeholders}) AND user_id IS NULL', (instance_id, *aliases)).fetchall():
            identity = owner(result['sessions'], row['source_session_id'])
            uid = mapping.get((identity['platform'], identity['external_id'])) if identity else None
            if uid:
                report['sessions'] += connection.execute('UPDATE sessions SET user_id=?,department_id=coalesce(department_id,?) WHERE session_key=? AND user_id IS NULL', (uid, department_at(connection, uid, row['started_at']), row['session_key'])).rowcount
        connection.execute("INSERT INTO plugin_settings(key,value_json) VALUES('people_sync',?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json", (json.dumps(report),))
        if actor is not None or any(report[k] for k in ('created', 'requests', 'tools', 'sessions')):
            from .admin import audit
            from .security import Principal
            audit(connection, actor or Principal('people-sync', 'admin'), 'people.sync', instance_id, json.dumps(report))
    return report
