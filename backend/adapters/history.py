"""Read saved Hermes lifetime aggregates separately from physical requests."""
import sqlite3
from collections import defaultdict
from pathlib import Path

from ..config import hermes_home


def user_history(connection, department_id='', user_id='', *, home=None, profile_name=None):
    home = (home or hermes_home()).resolve()
    path = home / 'state.db'
    unavailable = {'available': False, 'source': 'hermes_session_model_usage', 'scope': 'current_hermes_home', 'users': [], 'message': '当前 Hermes Home 没有可读取的历史用量汇总'}
    if not path.is_file() or path.resolve().parent != home:
        return unavailable
    if profile_name is None:
        import hermes_constants
        profile_name = getattr(hermes_constants, 'profile_name_for_home', lambda value: None)(home)
        if profile_name is None and home == (Path.home() / '.hermes').resolve():
            profile_name = 'default'
    if profile_name is None:
        return unavailable
    users = {r['id']: dict(r) for r in connection.execute('SELECT id,name,platform,external_id,department_id FROM users')}
    mapping = {(u['platform'], u['external_id']): u['id'] for u in users.values()}
    core = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2.5)
    try:
        core.row_factory = sqlite3.Row
        core.execute('PRAGMA query_only=ON')
        core.execute('BEGIN')
        sessions = core.execute('SELECT id,source,user_id,parent_session_id,profile_name FROM sessions').fetchmany(100001)
        records = core.execute('SELECT session_id,input_tokens,cache_read_tokens,cache_write_tokens,output_tokens,api_call_count FROM session_model_usage').fetchmany(100001)
    finally:
        core.close()
    if len(sessions) > 100000 or len(records) > 100000:
        raise ValueError('History exceeds bounded read')
    owned = {r['id']: r for r in sessions if r['profile_name'] in (None, profile_name)}
    def owner(sid):
        seen = set()
        while sid in owned and sid not in seen:
            seen.add(sid)
            row = owned[sid]
            uid = mapping.get((row['source'], row['user_id']))
            if uid:
                return uid
            if row['source'] != 'subagent':
                break
            sid = row['parent_session_id']
        return ''
    grouped = defaultdict(lambda: {'tokens': 0, 'api_calls': 0, 'sessions': set(), 'unknown_rows': 0, 'known_rows': 0})
    for row in records:
        if row['session_id'] not in owned:
            continue
        uid = owner(row['session_id'])
        if user_id and uid != user_id:
            continue
        if department_id and users.get(uid, {}).get('department_id') != department_id:
            continue
        target = grouped[uid]
        target['sessions'].add(row['session_id'])
        counts = [row[k] for k in ('input_tokens', 'cache_read_tokens', 'cache_write_tokens', 'output_tokens')]
        if all(type(n) is int and n >= 0 for n in counts):
            target['tokens'] += sum(counts)
            target['known_rows'] += 1
        else:
            target['unknown_rows'] += 1
        if type(row['api_call_count']) is int and row['api_call_count'] >= 0:
            target['api_calls'] += row['api_call_count']
    result = [{'id': uid, 'name': users.get(uid, {}).get('name', '未归属'), **{k: v for k, v in values.items() if k != 'known_rows'}, 'tokens': values['tokens'] if values['known_rows'] else None, 'sessions': len(values['sessions'])} for uid, values in grouped.items()]
    result.sort(key=lambda r: (r['tokens'] is None, -(r['tokens'] or 0), r['name']))
    return {'available': True, 'source': 'hermes_session_model_usage', 'scope': 'current_hermes_home', 'users': result[:100], 'total_users': len(result),
            'message': 'Hermes 已保存的历史汇总，包含主调用与辅助调用；独立展示，不与逐次采集记录相加。部门筛选按当前人员归属。'}
