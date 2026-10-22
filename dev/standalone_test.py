import os
import sys
import json
import sqlite3
from types import SimpleNamespace
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.standalone import create_app, initialize_auth

directory = tempfile.TemporaryDirectory(prefix='hum-standalone-browser-')
root = Path(directory.name)
hermes_home = root / 'hermes-home'
hermes_home.mkdir()
sys.modules['hermes_constants'] = SimpleNamespace(get_hermes_home=lambda: hermes_home, profile_name_for_home=lambda value: 'default')
with sqlite3.connect(hermes_home / 'state.db') as connection:
    connection.execute('CREATE TABLE sessions(id,source,user_id,profile_name,chat_type,parent_session_id,origin_json)')
    for sid, uid, name in [('write-regression', 'demo-auto', '自动发现用户'), ('people-unseen', 'demo-sync', '待同步用户')]:
        connection.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)', (sid, 'feishu', uid, 'default', 'dm', None, json.dumps({'platform': 'feishu', 'user_id': uid, 'user_name': name, 'chat_type': 'dm'})))
initialize_auth(root / 'credentials/auth.json', 'isolated-browser-password-2026')
os.environ.pop('USAGE_MANAGER_SESSION_CONTENT', None)
os.environ.pop('USAGE_MANAGER_TOOL_CONTENT', None)
app = create_app(root / 'credentials/auth.json', root / 'usage.sqlite3', 'http://127.0.0.1:9120')

# Synthetic regression data in this temporary database only; never a real Home.
from backend import admin, events
from backend.schemas import PriceBody
from backend.security import Principal

with app.state.hum_runtime.store.transaction() as connection:
    admin.save_price(connection, Principal('isolated-test', 'admin'), PriceBody(provider='write-test', model='cache-write-regression', input='0.1', cached='0.01', output='0.5', valid_from='2026-01-01'))
    events.ingest_model(connection, events.ModelEvent(instance_id='isolated-test', profile_id='default', source_event_id='write-regression', api_request_id='write-regression', session_id='write-regression', provider='write-test', model='cache-write-regression', occurred_at=datetime.now(timezone.utc), input_total_tokens=49079, cached_input_tokens=48134, cache_write_tokens=942, output_tokens=49, provider_usage_schema='hermes-canonical/source-525dbcad'))
