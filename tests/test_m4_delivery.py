import importlib
import importlib.util
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

from ops import manage
from scripts import package_release

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def artifact():
    subprocess.run([sys.executable, str(ROOT / 'scripts/package_release.py')], cwd=ROOT, check=True, capture_output=True)
    path = ROOT / 'build/hermes-usage-manager-0.6.0.zip'
    return path, manage.digest(path)


def rewrite(artifact, output, mutation):
    path, _ = artifact
    with ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    mutation(files)
    with ZipFile(output, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output, manage.digest(output)


def test_release_is_reproducible_and_contains_no_development_runtime(artifact):
    path, before = artifact
    subprocess.run([sys.executable, str(ROOT / 'scripts/package_release.py')], check=True, capture_output=True)
    assert manage.digest(path) == before
    result = manage.verified(path, before)
    assert result['version'] == '0.6.0'
    assert len(result['source_revision']) == 40
    assert isinstance(result['source_dirty'], bool)
    assert 'ops/manage.py' in result['files']
    assert {'install.sh', 'backend/config.py'} <= result['files'].keys()
    assert not any(name.startswith(('frontend/', 'dev/', 'fixtures/', 'tests/')) or name.endswith(('.db', '.pyc', '.sqlite3')) for name in result['files'])
    for line in path.with_suffix('.sha256').read_text().splitlines():
        checksum, name = line.split('  ')
        assert manage.digest(path.parent / name) == checksum


def test_stage_and_cli_work_without_checkout_or_node(artifact, tmp_path):
    path, checksum = artifact
    staged = tmp_path / 'staged'
    manage.stage(path, checksum, staged)
    helper = staged / manage.NAME / 'ops/manage.py'
    result = subprocess.run([sys.executable, str(helper), 'verify', str(path), '--sha256', checksum], cwd=tmp_path, env={**os.environ, 'PYTHONPATH': '', 'PATH': ''}, capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)['status'] == 'ok'
    with pytest.raises(ValueError):
        manage.stage(path, checksum, staged)


def test_runtime_install_tree_matches_release_and_keeps_security_tests_out_of_runtime(artifact, tmp_path):
    path, _ = artifact
    destination = tmp_path / 'install'
    with ZipFile(path) as archive:
        prefix = manage.NAME + '/'
        files = {name.removeprefix(prefix): archive.read(name) for name in archive.namelist()}
    package_release.write_install_tree(files, destination)
    assert manage.inventory(destination) == {name: package_release.checksum(data) for name, data in files.items()}
    assert (destination / 'install.sh').is_file()
    assert (destination / 'backend/standalone.py').read_bytes() == files['backend/standalone.py']
    assert not (destination / 'tests').exists()
    assert not (destination / 'frontend').exists()
    assert not (destination / 'dev').exists()
    before = manage.inventory(destination)
    with pytest.raises(FileExistsError):
        package_release.write_install_tree(files, destination)
    assert manage.inventory(destination) == before


@pytest.mark.parametrize('member', ['../escape', 'hermes-usage-manager/../../escape', '/absolute', 'hermes-usage-manager/a\\b', 'hermes-usage-manager/C:/secret', 'hermes-usage-manager/./a', 'hermes-usage-manager/CON', 'hermes-usage-manager/NUL.txt', 'hermes-usage-manager/ambiguous.'])
def test_archive_rejects_unsafe_paths_before_creating_output(artifact, tmp_path, member):
    path, checksum = rewrite(artifact, tmp_path / 'unsafe.zip', lambda files: files.update({member: b'bad'}))
    with pytest.raises(ValueError):
        manage.stage(path, checksum, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


@pytest.mark.parametrize('mutation', ['changed', 'extra', 'missing', 'case-duplicate', 'version'])
def test_archive_inventory_and_version_fail_closed(artifact, tmp_path, mutation):
    def mutate(files):
        if mutation == 'changed':
            files['hermes-usage-manager/__init__.py'] += b'\n'
        elif mutation == 'extra':
            files['hermes-usage-manager/secret.env'] = b'bad'
        elif mutation == 'missing':
            del files['hermes-usage-manager/__init__.py']
        elif mutation == 'case-duplicate':
            files['hermes-usage-manager/PLUGIN.yaml'] = b'bad'
        else:
            record = json.loads(files['hermes-usage-manager/release.json'])
            record['version'] = '999.0.0'
            files['hermes-usage-manager/release.json'] = json.dumps(record).encode()
    path, checksum = rewrite(artifact, tmp_path / 'bad.zip', mutate)
    with pytest.raises(ValueError):
        manage.verified(path, checksum)


def test_wrong_checksum_and_symlink_archive_are_rejected(artifact, tmp_path):
    with pytest.raises(ValueError):
        manage.verified(artifact[0], '0' * 64)
    path = tmp_path / 'link.zip'
    with ZipFile(path, 'w') as archive:
        entry = ZipInfo('hermes-usage-manager/link')
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, '../outside')
    with pytest.raises(ValueError):
        manage.stage(path, manage.digest(path), tmp_path / 'out')


def test_snapshot_uses_sqlite_backup_including_committed_wal_and_restores_offline(tmp_path):
    plugin = tmp_path / 'plugin'
    plugin.mkdir()
    (plugin / 'plugin.yaml').write_text('name: hermes-usage-manager\nversion: 0.4.4\n')
    database = tmp_path / 'live.sqlite3'
    from backend.db import Store
    Store(database)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE evidence(value TEXT)')
        connection.execute("INSERT INTO evidence VALUES('committed-in-wal')")
        connection.commit()
        assert Path(str(database) + '-wal').is_file()
        saved = tmp_path / 'snapshot'
        manage.snapshot(plugin, database, saved)
    assert not (saved / 'usage.sqlite3-wal').exists()
    restored = tmp_path / 'restored'
    manage.restore(saved, restored)
    with closing(sqlite3.connect(restored / 'usage.sqlite3')) as connection:
        assert connection.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        assert connection.execute('SELECT value FROM evidence').fetchone()[0] == 'committed-in-wal'
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute('SELECT value FROM evidence').fetchone()[0] == 'committed-in-wal'
    if os.name != 'nt':
        assert restored.stat().st_mode & 0o077 == 0
        assert (restored / 'usage.sqlite3').stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError):
        manage.restore(saved, restored)
    (saved / 'usage.sqlite3').write_bytes(b'tampered')
    with pytest.raises(ValueError):
        manage.restore(saved, tmp_path / 'bad-restore')
    assert not (tmp_path / 'bad-restore').exists()


def test_isolated_upgrade_rollback_and_uninstall_preserve_database(artifact, tmp_path):
    plugin = tmp_path / manage.NAME
    plugin.mkdir()
    (plugin / 'plugin.yaml').write_text('name: hermes-usage-manager\nversion: 0.4.4\n')
    from backend.db import Store
    database = tmp_path / 'usage.sqlite3'
    store = Store(database)
    with store.transaction() as connection:
        connection.execute("INSERT INTO instances VALUES('test', 'preserved')")
    snapshot = tmp_path / 'snapshot'
    manage.snapshot(plugin, database, snapshot)
    staged = tmp_path / 'stage'
    manage.stage(*artifact, staged)
    plugin.rename(tmp_path / 'previous-plugin')
    (staged / manage.NAME).rename(plugin)
    spec = importlib.util.spec_from_file_location('m4_isolated_entry', plugin / 'dashboard/plugin_api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    upgraded = module.Runtime.__module__.rsplit('.', 1)[0]
    upgraded_store = importlib.import_module(upgraded + '.db').Store(database)
    with upgraded_store.read() as connection:
        assert connection.execute("SELECT name FROM instances WHERE id='test'").fetchone()[0] == 'preserved'
    restored = tmp_path / 'restore'
    manage.restore(snapshot, restored)
    plugin.rename(tmp_path / 'failed-plugin')
    (restored / manage.NAME).rename(plugin)
    database.rename(tmp_path / 'retired.sqlite3')
    (restored / 'usage.sqlite3').rename(database)
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT name FROM instances WHERE id='test'").fetchone()[0] == 'preserved'
    plugin.rename(tmp_path / 'uninstalled-plugin')
    assert not plugin.exists() and database.is_file()


@pytest.mark.parametrize('change', ['version', 'runtime', 'stale'])
def test_release_rejects_version_mismatch_or_stale_build(tmp_path, change):
    for relative in ('plugin.yaml', 'pyproject.toml', 'dashboard/manifest.json', 'frontend/package.json', 'backend/api.py', 'backend/responses.py', 'backend/adapters/hooks.py', 'frontend/src/services/api.ts'):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    if change == 'version':
        (tmp_path / 'frontend/package.json').write_text('{"version":"0.0.0"}')
    elif change == 'runtime':
        (tmp_path / 'backend/api.py').write_text('0.0.0')
    else:
        (tmp_path / 'build').mkdir()
        (tmp_path / 'build/release-inputs.json').write_text(json.dumps({'inputs': {'src/services/api.ts': '0' * 64}, 'outputs': {'ignored': '0' * 64}}))
    with pytest.raises(ValueError):
        package_release.collect(tmp_path)


def test_duplicate_members_and_oversized_archive_are_rejected(artifact, tmp_path, monkeypatch):
    duplicate = tmp_path / 'duplicate.zip'
    shutil.copyfile(artifact[0], duplicate)
    with ZipFile(duplicate, 'a') as archive, pytest.warns(UserWarning):
        archive.writestr('hermes-usage-manager/plugin.yaml', 'duplicate')
    with pytest.raises(ValueError):
        manage.verified(duplicate, manage.digest(duplicate))
    monkeypatch.setattr(manage, 'MAXIMUM_BYTES', 10)
    with pytest.raises(ValueError):
        manage.verified(*artifact)


def test_snapshot_rejects_nested_db_and_existing_output(tmp_path):
    plugin = tmp_path / 'plugin'
    plugin.mkdir()
    (plugin / 'plugin.yaml').touch()
    database = plugin / 'usage.sqlite3'
    database.touch()
    with pytest.raises(ValueError):
        manage.snapshot(plugin, database, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()
    external = tmp_path / 'external.sqlite3'
    with closing(sqlite3.connect(external)) as connection:
        connection.execute('CREATE TABLE evidence(value TEXT)')
    existing = tmp_path / 'existing'
    existing.mkdir()
    (existing / 'keep.txt').write_text('untouched')
    with pytest.raises(ValueError):
        manage.snapshot(plugin, external, existing)
    assert (existing / 'keep.txt').read_text() == 'untouched'


def test_inspect_db_is_read_only_and_returns_only_aggregate_metadata(tmp_path):
    from backend.db import Store
    path = tmp_path / 'usage.sqlite3'
    store = Store(path)
    with store.transaction() as connection:
        connection.execute("INSERT INTO instances VALUES('test', 'never printed')")
    before = manage.digest(path)
    result = manage.inspect_database(path)
    assert result['data_source'] == 'live'
    assert len(result['migrations']) == 5
    assert result['counts']['llm_requests'] == 0
    assert 'never printed' not in json.dumps(result)
    assert manage.digest(path) == before
    missing = tmp_path / 'missing.sqlite3'
    with pytest.raises(sqlite3.OperationalError):
        manage.inspect_database(missing)
    assert not missing.exists()


@pytest.mark.parametrize('dirty,tags', [(True, ['v0.6.0']), (False, [])])
def test_formal_publish_refuses_uncommitted_or_untagged_source_without_replacing_candidate(artifact, monkeypatch, dirty, tags):
    path, before = artifact
    def git_output(command, **options):
        return {'rev-parse': 'a' * 40, 'status': ' M pending' if dirty else '', 'tag': '\n'.join(tags)}[command[1]]
    monkeypatch.setattr(package_release.subprocess, 'check_output', git_output)
    with pytest.raises(ValueError, match='clean commit and matching'):
        package_release.main(['--require-tag'])
    assert manage.digest(path) == before


def test_formal_publish_records_clean_matching_tag_in_controlled_fixture(tmp_path, monkeypatch):
    def git_output(command, **options):
        return {'rev-parse': 'a' * 40, 'status': '', 'tag': 'v0.6.0\n'}[command[1]]
    monkeypatch.setattr(package_release, 'ROOT', tmp_path)
    monkeypatch.setattr(package_release, 'collect', lambda root: ('0.6.0', {'ops/manage.py': b'fixture'}))
    monkeypatch.setattr(package_release.subprocess, 'check_output', git_output)
    package_release.main(['--require-tag'])
    with ZipFile(tmp_path / 'build/hermes-usage-manager-0.6.0.zip') as archive:
        release = json.loads(archive.read('hermes-usage-manager/release.json'))
    assert release['source_tag'] == 'v0.6.0'
    assert release['source_dirty'] is False
    assert release['release_status'] == 'tagged'


def test_snapshot_refuses_core_state_db_and_unrecognized_database(tmp_path):
    plugin = tmp_path / 'plugin'
    plugin.mkdir()
    (plugin / 'plugin.yaml').touch()
    core = tmp_path / 'state.db'
    with closing(sqlite3.connect(core)) as connection:
        connection.execute('CREATE TABLE messages(content TEXT)')
    with pytest.raises(ValueError):
        manage.snapshot(plugin, core, tmp_path / 'core-backup')
    other = tmp_path / 'other.sqlite3'
    shutil.copyfile(core, other)
    with pytest.raises(sqlite3.OperationalError):
        manage.snapshot(plugin, other, tmp_path / 'other-backup')
    assert not (tmp_path / 'core-backup').exists()
    assert not (tmp_path / 'other-backup').exists()


def test_operator_cli_snapshot_inspect_and_restore_without_node_or_checkout(artifact, tmp_path):
    from backend.db import Store
    plugin = tmp_path / 'plugin'
    plugin.mkdir()
    (plugin / 'plugin.yaml').write_text('name: hermes-usage-manager\nversion: 0.4.4\n')
    database = tmp_path / 'usage.sqlite3'
    Store(database)
    helper = artifact[0].with_name('hermes-usage-manager-0.6.0-ops.py')
    snapshot = tmp_path / 'snapshot'
    restored = tmp_path / 'restored'
    commands = [
        ['snapshot', '--plugin', str(plugin), '--db', str(database), '--output', str(snapshot)],
        ['inspect-db', '--db', str(database)],
        ['inspect-db', '--db', str(snapshot / 'usage.sqlite3')],
        ['restore', str(snapshot), '--output', str(restored)],
        ['inspect-db', '--db', str(restored / 'usage.sqlite3')],
    ]
    for command in commands:
        result = subprocess.run([sys.executable, '-I', str(helper), *command], cwd=tmp_path, env={**os.environ, 'PATH': '', 'PYTHONPATH': ''}, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report['status'] == 'ok'
        if command[0] == 'inspect-db':
            assert report['data_source'] == 'live'
            assert report['counts']['llm_requests'] == 0
    assert (restored / manage.NAME / 'plugin.yaml').read_bytes() == (plugin / 'plugin.yaml').read_bytes()
    result = subprocess.run([sys.executable, '-I', str(helper), 'restore', str(snapshot), '--output', str(restored)], cwd=tmp_path, env={**os.environ, 'PATH': '', 'PYTHONPATH': ''}, capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stderr)['code'] == 'OUTPUT_EXISTS'


def test_snapshot_inventory_stays_valid_after_repeated_inspection(tmp_path):
    from backend.db import Store
    plugin = tmp_path / 'plugin'
    plugin.mkdir()
    (plugin / 'plugin.yaml').touch()
    database = tmp_path / 'live.sqlite3'
    Store(database)
    with closing(sqlite3.connect(database)) as writer:
        writer.execute("INSERT INTO instances VALUES('test', 'committed WAL data')")
        writer.commit()
        snapshot = tmp_path / 'snapshot'
        manage.snapshot(plugin, database, snapshot)
        before = manage.inventory(snapshot)
        for _ in range(3):
            manage.inspect_database(snapshot / 'usage.sqlite3')
        assert manage.inventory(snapshot) == before
        assert not (snapshot / 'usage.sqlite3-wal').exists()
        assert not (snapshot / 'usage.sqlite3-shm').exists()
        with closing(sqlite3.connect((snapshot / 'usage.sqlite3').as_uri() + '?mode=ro', uri=True)) as reader:
            assert reader.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
            assert reader.execute('SELECT name FROM instances').fetchone()[0] == 'committed WAL data'
        manage.restore(snapshot, tmp_path / 'restored')
        assert manage.inventory(snapshot) == before
        assert writer.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'


def test_legacy_wal_snapshot_remains_strict_and_untouched_after_inspection(tmp_path):
    from backend.db import Store
    plugin = tmp_path / 'legacy' / manage.NAME
    plugin.mkdir(parents=True)
    (plugin / 'plugin.yaml').touch()
    source_path = tmp_path / 'live.sqlite3'
    Store(source_path)
    snapshot = plugin.parent
    database = snapshot / 'usage.sqlite3'
    with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(database)) as target:
        source.backup(target)
    metadata = {'format': 1, 'files': manage.inventory(snapshot)}
    (snapshot / 'snapshot.json').write_text(json.dumps(metadata))
    original = manage.digest(database)
    manage.inspect_database(database)
    assert (snapshot / 'usage.sqlite3-wal').exists()
    with pytest.raises(manage.OperationError) as error:
        manage.restore(snapshot, tmp_path / 'restored')
    assert error.value.code == 'SNAPSHOT_INVENTORY_MISMATCH'
    assert manage.digest(database) == original
    assert (snapshot / 'usage.sqlite3-wal').exists()
    assert not (tmp_path / 'restored').exists()


def test_restore_existing_output_reports_specific_error_code(tmp_path):
    from backend.db import Store
    plugin = tmp_path / 'plugin'
    plugin.mkdir()
    (plugin / 'plugin.yaml').touch()
    database = tmp_path / 'live.sqlite3'
    Store(database)
    snapshot = tmp_path / 'snapshot'
    manage.snapshot(plugin, database, snapshot)
    existing = tmp_path / 'existing'
    existing.mkdir()
    with pytest.raises(manage.OperationError) as error:
        manage.restore(snapshot, existing)
    assert error.value.code == 'OUTPUT_EXISTS'


@pytest.mark.parametrize('relative', ['standalone/dist/app.js', 'frontend/src/standalone.tsx', 'frontend/scripts/build-standalone.mjs'])
def test_standalone_build_inputs_and_outputs_are_checked_before_release(artifact, monkeypatch, relative):
    original = package_release.checksum
    changed = (ROOT / relative).read_bytes()
    monkeypatch.setattr(package_release, 'checksum', lambda data: 'changed' if data == changed else original(data))
    with pytest.raises(ValueError, match='Build inputs or outputs changed'):
        package_release.collect(ROOT)
