import atexit
import json
import logging
import os
import queue
import socket
import sqlite3
import sys
import threading
from time import monotonic
from collections import Counter
from pathlib import Path
from uuid import uuid4

from .adapters.hooks import HOOKS, HookContext, Normalizer, identifier
from .db import Store, now
from .config import collection_enabled, database_path
from .events import ModelEvent, ToolEvent, ingest_model, ingest_tool, key

logger = logging.getLogger('hermes-usage-manager')


def local_instance():
    return os.environ.get('USAGE_MANAGER_INSTANCE_ID') or 'instance-' + key(socket.gethostname(), str(Path.home()))[:24]


def context():
    import hermes_constants
    home = hermes_constants.get_hermes_home().expanduser().resolve()
    profile_name = getattr(hermes_constants, 'profile_name_for_home', lambda value: None)
    profile = os.environ.get('USAGE_MANAGER_PROFILE_ID') or profile_name(home) or 'home-' + key(str(home))[:20]
    path = database_path()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError('INVALID_DB_PATH')
    return HookContext(local_instance(), profile, str(candidate.resolve()))


def classify_tool(name):
    module = sys.modules.get('tools.registry')
    registry = getattr(module, 'registry', None)
    if registry is None:
        return 'unknown', None
    toolset = registry.get_toolset_for_tool(name)
    if isinstance(toolset, str) and toolset.startswith('mcp-') and len(toolset) > 4:
        return 'mcp', toolset[4:]
    if isinstance(toolset, str) and toolset.lower().startswith('mcp'):
        return 'unknown', None
    return ('local', None) if toolset else ('unknown', None)


class Collector:
    def __init__(self, path, capacity=1024, retry_limit=3, start=True, source='live'):
        self.path = path
        self.source = source
        self.buffer = queue.Queue(maxsize=capacity)
        self.retry_limit = retry_limit
        self.run_id = uuid4().hex
        self.states = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        self.next_people_sync = 0
        self.store = None
        self.storage_failed = False
        if start:
            self.thread = threading.Thread(target=self.run, name='hum-collector', daemon=True)
            self.thread.start()

    def note(self, scope, field=None):
        with self.lock:
            record = self.states.setdefault((scope.instance_id, scope.profile_id), {'counters': Counter(), 'started': now(), 'seen': now(), 'success': None})
            record['seen'] = now()
            if field:
                record['counters'][field] += 1
        self.wake.set()

    def submit(self, scope, event):
        self.note(scope)
        if event is None:
            return
        try:
            self.buffer.put_nowait((scope, event, 0))
            self.note(scope, 'accepted')
        except queue.Full:
            self.note(scope, 'dropped')
            if self.snapshot()[0][1]['counters'].get('dropped', 0) == 1:
                logger.warning('Usage metadata buffer full; events dropped; see data quality counters')
        self.wake.set()

    def persist(self, scope, event):
        kind = 'model' if isinstance(event, ModelEvent) else 'tool'
        event_key = key(event.instance_id, event.profile_id, kind, event.source_event_id)
        with self.store.transaction() as connection:
            if connection.execute("SELECT count(*) FROM collection_queue WHERE status='pending'").fetchone()[0] >= 4096:
                self.note(scope, 'dropped')
                return
            connection.execute('INSERT OR IGNORE INTO collection_queue(event_key,kind,payload_json,received_at) VALUES(?,?,?,?)', (event_key, kind, event.model_dump_json(), now()))
            connection.execute("INSERT OR IGNORE INTO event_inbox(event_key,type,received_at,status) VALUES(?,?,?,'pending')", (event_key, kind, now()))

    def drain(self):
        processed = 0
        for _ in range(64):
            with self.store.transaction() as connection:
                row = connection.execute("SELECT * FROM collection_queue WHERE status='pending' ORDER BY received_at,event_key LIMIT 1").fetchone()
                if row is None:
                    break
                try:
                    event = (ModelEvent if row['kind'] == 'model' else ToolEvent).model_validate_json(row['payload_json'])
                    connection.execute('SAVEPOINT ingest_event')
                    (ingest_model if row['kind'] == 'model' else ingest_tool)(connection, event)
                    connection.execute('RELEASE SAVEPOINT ingest_event')
                except sqlite3.OperationalError:
                    raise
                except Exception:
                    try:
                        connection.execute('ROLLBACK TO SAVEPOINT ingest_event')
                        connection.execute('RELEASE SAVEPOINT ingest_event')
                    except Exception:
                        pass
                    attempts = row['attempts'] + 1
                    connection.execute("UPDATE collection_queue SET attempts=?,status=?,last_error='NORMALIZATION_OR_CONSTRAINT',payload_json=CASE WHEN ? THEN NULL ELSE payload_json END WHERE event_key=?", (attempts, 'failed' if attempts >= self.retry_limit else 'pending', attempts >= self.retry_limit, row['event_key']))
                    if attempts >= self.retry_limit:
                        connection.execute("UPDATE event_inbox SET status='failed',error_code='NORMALIZATION_OR_CONSTRAINT' WHERE event_key=?", (row['event_key'],))
                    continue
                connection.execute("UPDATE collection_queue SET status='done',payload_json=NULL,last_error=NULL WHERE event_key=?", (row['event_key'],))
                processed += 1
                self.note(HookContext(event.instance_id, event.profile_id, self.path))
                with self.lock:
                    state = self.states.get((event.instance_id, event.profile_id))
                    if state:
                        state['success'] = now()
        return processed

    def snapshot(self):
        with self.lock:
            return [(identity, {'counters': dict(state['counters']), 'started': state['started'], 'seen': state['seen'], 'success': state['success']}) for identity, state in self.states.items()]

    def heartbeat(self):
        expected = json.loads(os.environ.get('USAGE_MANAGER_EXPECTED_PROFILES', '[]'))
        if not isinstance(expected, list) or len(expected) > 100:
            raise ValueError('INVALID_PROFILE_INVENTORY')
        expected = [identifier(profile, required=True) for profile in expected]
        with self.store.transaction() as connection:
            for (instance, profile), state in self.snapshot():
                connection.execute('INSERT OR IGNORE INTO instances VALUES(?,?)', (instance, instance))
                for expected_profile in expected:
                    connection.execute('INSERT OR IGNORE INTO profiles(instance_id,id,display_name) VALUES(?,?,?)', (instance, expected_profile, expected_profile))
                connection.execute('INSERT OR IGNORE INTO profiles(instance_id,id,display_name) VALUES(?,?,?)', (instance, profile, profile))
                counts = state['counters']
                connection.execute('INSERT INTO collector_runs VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen,last_success=excluded.last_success,accepted=excluded.accepted,dropped=excluded.dropped,invalid=excluded.invalid,context_missing=excluded.context_missing', (key(self.run_id, instance, profile), instance, profile, state['started'], now(), state['success'], counts.get('accepted', 0), counts.get('dropped', 0), counts.get('invalid', 0), counts.get('context_missing', 0), json.dumps(HOOKS)))
            connection.execute("DELETE FROM collection_queue WHERE status='done' AND event_key NOT IN (SELECT event_key FROM collection_queue WHERE status='done' ORDER BY received_at DESC LIMIT 10000)")
            connection.execute("DELETE FROM collection_queue WHERE status='failed' AND event_key NOT IN (SELECT event_key FROM collection_queue WHERE status='failed' ORDER BY received_at DESC LIMIT 256)")

    def tick(self):
        if self.store is None:
            self.store = Store(self.path, self.source)
        for _ in range(64):
            try:
                scope, event, failures = self.buffer.get_nowait()
            except queue.Empty:
                break
            try:
                self.persist(scope, event)
            except Exception:
                if failures + 1 < self.retry_limit:
                    try:
                        self.buffer.put_nowait((scope, event, failures + 1))
                    except queue.Full:
                        self.note(scope, 'dropped')
                else:
                    self.note(scope, 'dropped')
                raise
            finally:
                self.buffer.task_done()
        self.drain()
        self.heartbeat()
        if self.source == 'live' and monotonic() >= self.next_people_sync:
            self.next_people_sync = monotonic() + 60
            try:
                from .people import sync
                sync(self.store)
            except (OSError, ValueError, sqlite3.Error):
                logger.warning('People metadata sync unavailable; model/tool collection continues')
        self.storage_failed = False

    def run(self):
        while not self.stop.is_set() or not self.buffer.empty():
            try:
                self.tick()
            except Exception:
                if not self.storage_failed:
                    logger.warning('Usage metadata storage unavailable; recovery is bounded; no raw payload logged')
                self.storage_failed = True
            self.wake.wait(1)
            self.wake.clear()
            if self.stop.is_set() and self.storage_failed:
                break

    def close(self, timeout=1):
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout)


class Dispatcher:
    def __init__(self, context_factory=context, enabled=None, classifier=classify_tool, source='live'):
        self.context_factory = context_factory
        self.enabled = enabled
        self.source = source
        self.normalizer = Normalizer(classifier)
        self.collectors = {}
        self.lock = threading.Lock()
        self.failures = Counter()

    def callback(self, name, payload=None, **fields):
        payload = fields if payload is None else payload
        try:
            if not (self.enabled if self.enabled is not None else collection_enabled()):
                return None
            scope = self.context_factory()
            with self.lock:
                collector = self.collectors.get(scope.db_path)
                if collector is None:
                    if len(self.collectors) >= 8:
                        self.failures['path_limit'] += 1
                        return None
                    collector = Collector(scope.db_path, source=self.source)
                    self.collectors[scope.db_path] = collector
            try:
                event = self.normalizer.normalize(name, payload, scope)
            except Exception:
                collector.note(scope, 'invalid')
                return None
            collector.submit(scope, event)
            if event is not None and event.external_user_id is None:
                collector.note(scope, 'context_missing')
        except Exception:
            self.failures['context_unavailable'] += 1
            if self.failures['context_unavailable'] == 1:
                logger.warning('Usage metadata context unavailable; verify Hermes adapter and path configuration')
        return None

    def close(self):
        for collector in list(self.collectors.values()):
            collector.close()


dispatcher = Dispatcher()
atexit.register(dispatcher.close)


def register(ctx):
    def handler(name):
        def callback(**kwargs):
            return dispatcher.callback(name, kwargs)
        return callback
    for name in HOOKS:
        ctx.register_hook(name, handler(name))
