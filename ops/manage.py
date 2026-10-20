"""Offline release verification, staging and consistent backups; never overwrite a target."""

import argparse
import hashlib
import io
import json
import os
import shutil
import sqlite3
import stat
import sys
import time
from contextlib import closing
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

NAME = 'hermes-usage-manager'
MAXIMUM_BYTES = 64 * 1024 * 1024


class OperationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def absolute(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Use an absolute path without parent traversal')
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or (ancestor.exists() and ancestor.resolve() != ancestor.absolute()):
            raise ValueError('Symlink or redirected paths are not allowed')
    return path.resolve()


def private(path, directory=False):
    if os.name != 'nt':
        path.chmod(0o700 if directory else 0o600)


def fresh(value):
    path = absolute(value)
    if path.exists():
        raise OperationError('OUTPUT_EXISTS', 'Choose a new output directory; existing targets are never overwritten')
    if not path.parent.is_dir():
        raise ValueError('Output parent must exist and output must not exist')
    path.mkdir(mode=0o700)
    return path


def inventory(root):
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Symlink or redirected member rejected')
        if path.is_file():
            files[path.relative_to(root).as_posix()] = digest(path)
        elif not path.is_dir():
            raise ValueError('Special filesystem member rejected')
    return files


def safe_member(name):
    path = PurePosixPath(name)
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{prefix}{number}' for prefix in ('COM', 'LPT') for number in range(1, 10)}
    if not name or '\\' in name or ':' in name or '\x00' in name or path.is_absolute() or '..' in path.parts or str(path) != name or any(part.endswith((' ', '.')) or part.split('.')[0].upper() in reserved for part in path.parts):
        raise ValueError('Unsafe archive member')
    return path


def archive_bytes(archive_path, expected):
    path = absolute(archive_path)
    with path.open('rb') as stream:
        data = stream.read(MAXIMUM_BYTES + 1)
    if len(data) > MAXIMUM_BYTES or len(expected) != 64 or any(character not in '0123456789abcdef' for character in expected) or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Archive SHA256 mismatch')
    return data


def verified_bytes(data):
    with ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) > 2048 or len(set(name.casefold() for name in names)) != len(names) or sum(member.file_size for member in members) > MAXIMUM_BYTES:
            raise ValueError('Archive size, count or duplicate member rejected')
        for member in members:
            parsed = safe_member(member.filename)
            mode = member.external_attr >> 16
            if parsed.parts[0] != NAME or len(parsed.parts) < 2 or member.is_dir() or member.flag_bits & 1 or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                raise ValueError('Unsupported archive member')
        release = json.loads(archive.read(f'{NAME}/release.json'))
        if not isinstance(release, dict) or release.get('format') != 1 or release.get('name') != NAME or not isinstance(release.get('files'), dict):
            raise ValueError('Unsupported release manifest')
        expected_names = {f'{NAME}/{name}' for name in release['files']} | {f'{NAME}/release.json'}
        if set(names) != expected_names:
            raise ValueError('Release inventory mismatch')
        for name, checksum in release['files'].items():
            safe_member(name)
            if hashlib.sha256(archive.read(f'{NAME}/{name}')).hexdigest() != checksum:
                raise ValueError('Release member checksum mismatch')
        dashboard = json.loads(archive.read(f'{NAME}/dashboard/manifest.json'))
        if dashboard.get('version') != release.get('version') or dashboard.get('name') not in (None, NAME):
            raise ValueError('Release version mismatch')
        return release


def verified(archive_path, expected):
    return verified_bytes(archive_bytes(archive_path, expected))


def stage(archive_path, expected, output):
    data = archive_bytes(archive_path, expected)
    release = verified_bytes(data)
    destination = fresh(output)
    with ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            target = destination.joinpath(*PurePosixPath(member.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with archive.open(member) as source, target.open('xb') as stream:
                shutil.copyfileobj(source, stream)
            private(target)
    return release


def copy_private(source, destination):
    destination.mkdir(mode=0o700)
    shutil.copytree(source, destination, dirs_exist_ok=True)
    for path in (destination, *destination.rglob('*')):
        private(path, path.is_dir())


def snapshot(plugin, database, output):
    plugin, database, output = absolute(plugin), absolute(database), absolute(output)
    if not (plugin / 'plugin.yaml').is_file() or not database.is_file() or database.name == 'state.db' or database.is_relative_to(plugin) or output.is_relative_to(plugin) or output.exists():
        raise ValueError('Expected installed plugin and existing external database')
    summary = inspect_database(database)
    inventory(plugin)
    destination = fresh(output)
    copy_private(plugin, destination / NAME)
    saved = destination / 'usage.sqlite3'
    saved.touch(mode=0o600, exist_ok=False)
    deadline = time.monotonic() + 30
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise ValueError('SQLite backup exceeded 30 seconds; stop writers before retrying')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=5)) as source:
        source.execute('PRAGMA query_only=ON')
        with closing(sqlite3.connect(saved)) as target:
            source.backup(target, pages=128, progress=progress)
            if target.execute('PRAGMA journal_mode=DELETE').fetchone()[0].lower() != 'delete':
                raise OperationError('SNAPSHOT_SEAL_FAILED', 'Snapshot must be self-contained before hashing')
            if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite snapshot integrity check failed')
    metadata = {'format': 1, 'files': inventory(destination), 'database_source': str(database), 'data_source': summary['data_source'], 'database_journal': 'delete'}
    record = destination / 'snapshot.json'
    record.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    private(record)
    return metadata


def restore(snapshot_path, output):
    source = absolute(snapshot_path)
    metadata = json.loads((source / 'snapshot.json').read_text(encoding='utf-8'))
    actual = inventory(source)
    actual.pop('snapshot.json', None)
    if metadata.get('format') != 1 or actual != metadata.get('files'):
        raise OperationError('SNAPSHOT_INVENTORY_MISMATCH', 'Snapshot files changed; preserve the snapshot and create a new one from the unchanged source')
    if not (source / NAME / 'plugin.yaml').is_file() or not (source / 'usage.sqlite3').is_file():
        raise ValueError('Snapshot is incomplete')
    destination = absolute(output)
    if destination.exists():
        raise OperationError('OUTPUT_EXISTS', 'Choose a new output directory; existing targets are never overwritten')
    if not destination.parent.is_dir() or destination.is_relative_to(source):
        raise ValueError('Restore requires a new output outside the snapshot')
    copy_private(source, destination)
    return metadata


def inspect_database(database):
    path = absolute(database)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        source = json.loads(connection.execute("SELECT value_json FROM plugin_settings WHERE key='data_source'").fetchone()[0])
        if source not in ('live', 'mock'):
            raise ValueError('Unrecognized database source')
        counts = {table: connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in ('llm_requests', 'tool_calls', 'sessions', 'profiles', 'model_prices', 'audit_access_logs')}
        migrations = [row[0] for row in connection.execute('SELECT version FROM schema_migrations ORDER BY version LIMIT 32')]
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
    return {'data_source': source, 'migrations': migrations, 'counts': counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('verify', 'stage'):
        action = commands.add_parser(command)
        action.add_argument('archive', type=Path)
        action.add_argument('--sha256', required=True)
        if command == 'stage':
            action.add_argument('--output', type=Path, required=True)
    action = commands.add_parser('snapshot')
    action.add_argument('--plugin', type=Path, required=True)
    action.add_argument('--db', type=Path, required=True)
    action.add_argument('--output', type=Path, required=True)
    action = commands.add_parser('restore')
    action.add_argument('snapshot', type=Path)
    action.add_argument('--output', type=Path, required=True)
    action = commands.add_parser('inspect-db')
    action.add_argument('--db', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'verify':
            result = verified(args.archive, args.sha256)
        elif args.command == 'stage':
            result = stage(args.archive, args.sha256, args.output)
        elif args.command == 'snapshot':
            result = snapshot(args.plugin, args.db, args.output)
        elif args.command == 'restore':
            result = restore(args.snapshot, args.output)
        else:
            result = inspect_database(args.db)
        if args.command == 'inspect-db':
            summary = result
        elif args.command in ('snapshot', 'restore'):
            summary = {'database_journal': result.get('database_journal', 'unknown'), 'snapshot_format': result['format']}
        else:
            summary = {'version': result.get('version')}
        print(json.dumps({'status': 'ok', 'operation': args.command, **summary}, ensure_ascii=False))
    except OperationError as error:
        print(json.dumps({'status': 'error', 'operation': args.command, 'code': error.code, 'message': str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from None
    except (OSError, ValueError, KeyError, BadZipFile, sqlite3.Error) as error:
        raise SystemExit(f'Operation failed ({type(error).__name__}); existing targets are not overwritten') from None


if __name__ == '__main__':
    main()
