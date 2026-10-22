"""Bounded, read-only identity metadata from this Hermes Home. No message reads."""

import json
import hashlib
import os
import sqlite3
from pathlib import Path

from ..config import hermes_home


def text(value, maximum=100):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        return None
    return value.strip()


def metadata(*, home=None, profile_name=None, session_id=None):
    home = (home or hermes_home()).resolve()
    path = home / 'state.db'
    unavailable = {'available': False, 'profile': None, 'sessions': {}, 'message': '当前 Hermes Home 没有可读取的会话身份元数据'}
    if not path.is_file() or path.resolve().parent != home:
        return unavailable
    if profile_name is None:
        try:
            import hermes_constants
            profile_name = getattr(hermes_constants, 'profile_name_for_home', lambda value: None)(home)
        except ImportError:
            pass
        if profile_name is None and home == (Path.home() / '.hermes').resolve():
            profile_name = 'default'
    if profile_name is None:
        return unavailable
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=0.5)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        columns = {r[1] for r in connection.execute('PRAGMA table_info(sessions)')}
        if not {'id', 'source', 'user_id', 'profile_name'}.issubset(columns):
            return unavailable
        wanted = ['id', 'source', 'user_id', 'profile_name']
        wanted += [k for k in ('parent_session_id', 'origin_json', 'chat_type') if k in columns]
        if session_id is None:
            rows = connection.execute('SELECT ' + ','.join(wanted) + ' FROM sessions WHERE profile_name=? OR profile_name IS NULL LIMIT 10001', (profile_name,)).fetchall()
        else:
            # Only this session and an explicit parent chain, never unrelated rows.
            rows, seen, sid = [], set(), session_id
            for _ in range(32):
                if not sid or sid in seen:
                    break
                seen.add(sid)
                row = connection.execute('SELECT ' + ','.join(wanted) + ' FROM sessions WHERE id=? AND (profile_name=? OR profile_name IS NULL)', (sid, profile_name)).fetchone()
                if row is None:
                    break
                rows.append(row)
                sid = row['parent_session_id'] if row['source'] == 'subagent' and 'parent_session_id' in columns else None
        if len(rows) > 10000:
            return unavailable | {'message': '会话身份超过单次同步上限 10000，未执行同步'}
    finally:
        connection.close()
    sessions = {raw['id']: parse_session(raw, profile_name) for raw in rows}
    legacy = 'home-' + hashlib.sha256(json.dumps((str(home),), ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()[:20]
    aliases = list(dict.fromkeys([profile_name, legacy, *([os.environ['USAGE_MANAGER_PROFILE_ID']] if os.environ.get('USAGE_MANAGER_PROFILE_ID') else [])]))
    return {'available': True, 'profile': profile_name, 'aliases': aliases, 'sessions': sessions, 'message': '仅读取当前 Hermes Home 的会话身份元数据'}


def owner(sessions, session_id):
    seen = set()
    while session_id in sessions and session_id not in seen and len(seen) < 32:
        seen.add(session_id)
        row = sessions[session_id]
        if row['platform'] == 'subagent':
            session_id = row['parent']
            continue
        return row if row['direct'] and row['platform'] and row['external_id'] else None
    return None


def parse_session(raw, profile_name):
    row = dict(raw)
    origin = {}
    if isinstance(row.get('origin_json'), str) and len(row['origin_json']) <= 16384:
        try:
            parsed = json.loads(row['origin_json'])
            origin = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            pass
    platform, external = text(row['source'], 50), text(row['user_id'])
    consistent = origin.get('user_id') in (None, external) and origin.get('platform') in (None, platform)
    types = [str(value).lower() for value in (row.get('chat_type'), origin.get('chat_type')) if value]
    direct = bool(types) and all(value in {'dm', 'private', 'direct'} for value in types) and consistent
    name = text(origin.get('user_name'), 50) if consistent else None
    return {'platform': platform, 'external_id': external, 'name': name if name != external else None,
                               'direct': direct, 'parent': row.get('parent_session_id'), 'profile': profile_name}
