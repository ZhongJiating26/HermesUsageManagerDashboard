"""Private, immutable copies of transcript attachments (never serve source paths)."""
import hashlib
import json
import logging
import os
import re
import sqlite3
import stat
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone

from .config import hermes_home, database_path

log = logging.getLogger(__name__)


def references(role, content):
    if role not in ('user', 'assistant') or not isinstance(content, str):
        return []
    found = []
    if role == 'assistant':
        found += [(Path(p.strip('"\'' )).name, p.strip('"\'')) for p in re.findall(r'(?:^|\n)\s*MEDIA:\s*([^\r\n]+)', content)]
    else:
        found += re.findall(r"\[The user sent (?:a document|a text document|an audio file attachment|a video attachment): '([^']+)'. It is saved at: (.+?)\. (?:Its text|To read|This|You)", content)
        found += re.findall(r"\[(?:image|video|audio|document) '([^']+)' saved at: ([^\]\r\n]+)\]", content)
        found += [(Path(p).name, p) for p in re.findall(r"(?:image_url: |voice message: )(/[^\]\r\n]+?)(?: ~\]| \(duration:|\])", content)]
        found += [(Path(p).name, p) for p in re.findall(r'The file is also saved at: (/[^\]\r\n]+)\]', content)]
    return list(dict.fromkeys(found))


def display_text(role, content, files):
    """Replace transport annotations only after matching snapshot records exist."""
    if not isinstance(content, str) or not files:
        return content
    for name, source in references(role, content):
        if not any(f['name'] == Path(name).name for f in files):
            continue
        if role == 'assistant':
            content = re.sub(r'(?m)^\s*MEDIA:\s*' + re.escape(source) + r'\s*$', '', content)
        else:
            content = re.sub(r"\[The user sent [^\]\r\n]*?It is saved at: " + re.escape(source) + r"\. [^\]]*\]", '', content)
            content = re.sub(r"\[(?:image|video|audio|document) '[^']*' saved at: " + re.escape(source) + r"\]", '', content)
            content = content.replace('[Attachment: ' + name + ']', '')
    return content.strip()


class Archive:
    def __init__(self, root=None):
        self.root = Path(root) if root else database_path().parent / 'attachments'
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def connect(self):
        c = sqlite3.connect(self.root / 'index.sqlite3', timeout=30)
        c.row_factory = sqlite3.Row
        c.execute('CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, scope TEXT, session TEXT, message TEXT, direction TEXT, name TEXT, source TEXT, status TEXT, size INTEGER, sha256 TEXT, captured_at TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS cursors (scope TEXT PRIMARY KEY, last_id INTEGER)')
        os.chmod(self.root / 'index.sqlite3', 0o600)
        return c

    def capture(self, home, session, message, role, content):
        home = Path(home).resolve()
        scope = str(home)
        for name, source in references(role, content):
            identity = hashlib.sha256(json.dumps([scope, session, str(message), source]).encode()).hexdigest()
            with self.connect() as c:
                old = c.execute('SELECT status FROM files WHERE id=?', (identity,)).fetchone()
                if old and old['status'] == 'ready':
                    continue
            status, size, digest = 'missing', None, None
            temp = None
            try:
                path = Path(source).expanduser()
                # Transcript text is untrusted. Only gateway cache attachments
                # can be copied; symlinks and arbitrary host files are excluded.
                allowed = home / 'cache'
                if not path.is_absolute() or not path.resolve().is_relative_to(allowed.resolve()):
                    status = 'blocked'
                else:
                    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
                    with os.fdopen(fd, 'rb') as incoming:
                        before = os.fstat(incoming.fileno())
                        if not stat.S_ISREG(before.st_mode):
                            raise OSError('Not a regular file')
                        outfd, temp = tempfile.mkstemp(dir=self.root)
                        hasher = hashlib.sha256()
                        with os.fdopen(outfd, 'wb') as outgoing:
                            while chunk := incoming.read(1024 * 1024):
                                outgoing.write(chunk)
                                hasher.update(chunk)
                            outgoing.flush()
                            os.fsync(outgoing.fileno())
                        after = os.fstat(incoming.fileno())
                        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            raise OSError('Source changed during snapshot')
                    digest, size = hasher.hexdigest(), after.st_size
                    os.replace(temp, self.root / identity)
                    temp = None
                    status = 'ready'
            except OSError:
                status = 'missing'
            finally:
                if temp:
                    Path(temp).unlink(missing_ok=True)
            with self.connect() as c:
                c.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?)', (identity, scope, session, str(message), 'received' if role == 'user' else 'sent', Path(name).name, source, status, size, digest, datetime.now(timezone.utc).isoformat()))

    def scan(self, home):
        home = Path(home).resolve()
        path = home / 'state.db'
        if not path.is_file():
            return
        with self.connect() as c:
            row = c.execute('SELECT last_id FROM cursors WHERE scope=?', (str(home),)).fetchone()
        last = row[0] if row else 0
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            rows = db.execute('SELECT id,session_id,role,content FROM messages WHERE id>? ORDER BY id LIMIT 1000', (last,)).fetchall()
        finally:
            db.close()
        for mid, session, role, body in rows:
            self.capture(home, session, mid, role, body)
        if rows:
            with self.connect() as c:
                c.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)', (str(home), rows[-1][0]))
        return len(rows)

    def listing(self, home, session):
        with self.connect() as c:
            return [dict(r) for r in c.execute('SELECT id,message,direction,name,status,size,sha256,captured_at FROM files WHERE scope=? AND session=? ORDER BY message,id', (str(Path(home).resolve()), session))]


def start_worker(root=None):
    stop = threading.Event()
    def run():
        archive = Archive(root)
        while not stop.is_set():
            try:
                homes = {hermes_home(), *map(Path, json.loads(os.environ.get('USAGE_MANAGER_SESSION_HOMES', '{}')).values())}
                homes.update(p.parent for p in (hermes_home() / 'profiles').glob('*/state.db'))
                busy = False
                for home in homes:
                    busy = archive.scan(home) == 1000 or busy
            except Exception:
                log.exception('Attachment snapshot scan failed')
                busy = False
            stop.wait(0.1 if busy else 2)
    thread = threading.Thread(target=run, name='hum-attachment-snapshots', daemon=True)
    thread.start()
    return stop
