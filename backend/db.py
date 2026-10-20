import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def utc(value):
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


class Store:
    def __init__(self, path, source="live"):
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise ValueError("Database path must be absolute")
        self.path = candidate.resolve()
        if self.path.is_relative_to(PLUGIN_ROOT):
            raise ValueError("Database must be outside plugin source/install directory")
        self.source = source
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != 'nt':
            parent_stat = self.path.parent.stat()
            if parent_stat.st_uid != os.getuid() or parent_stat.st_mode & 0o022:
                raise ValueError('Unsafe database parent directory')
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
            except FileExistsError:
                pass
        if self.path.exists() and os.name != "nt":
            stat = self.path.stat()
            if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
                raise ValueError("Unsafe database ownership or write permissions")
        with self.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)")
            migrations = sorted((Path(__file__).parent / "migrations").glob("*.sql"))
            known = {row["version"]: row["checksum"] for row in connection.execute("SELECT * FROM schema_migrations")}
            if set(known) - {migration.stem for migration in migrations}:
                raise ValueError("Database schema is newer than this plugin")
            for migration in migrations:
                script = migration.read_text(encoding="utf-8")
                checksum = hashlib.sha256(script.encode()).hexdigest()
                if migration.stem in known:
                    if known[migration.stem] != checksum:
                        raise ValueError("Applied migration checksum mismatch")
                    continue
                statement = ''
                for line in script.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ''
                if statement.strip():
                    raise ValueError('Incomplete migration statement')
                connection.execute("INSERT INTO schema_migrations VALUES(?,?,?)", (migration.stem, checksum, now()))
            row = connection.execute("SELECT value_json FROM plugin_settings WHERE key='data_source'").fetchone()
            if row and json.loads(row[0]) != source:
                raise ValueError("Refusing Mock/Live database mode mismatch")
            connection.execute("INSERT OR IGNORE INTO plugin_settings VALUES('data_source',?)", (json.dumps(source),))
            connection.execute("INSERT OR IGNORE INTO plugin_settings VALUES('timezone','\"Asia/Shanghai\"')")
        if os.name != "nt":
            os.chmod(self.path, 0o600)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=2.5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=2500")
        connection.create_function("local_day", 2, lambda value, zone: datetime.fromisoformat(value).astimezone(ZoneInfo(zone)).date().isoformat(), deterministic=True)
        return connection

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
        finally:
            connection.rollback()
            connection.close()
