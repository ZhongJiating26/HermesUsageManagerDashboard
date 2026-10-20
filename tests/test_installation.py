import json
import sys
from types import SimpleNamespace

import pytest

from backend import config, standalone
from backend.adapters.hermes import storage_path
from backend.collector import context
from backend.db import Store


@pytest.fixture
def installation(tmp_path, monkeypatch):
    home = tmp_path / 'hermes'
    monkeypatch.setitem(sys.modules, 'hermes_constants', SimpleNamespace(get_hermes_home=lambda: home))
    monkeypatch.setattr(standalone.Path, 'home', lambda: tmp_path)
    monkeypatch.delenv('USAGE_MANAGER_DB_PATH', raising=False)
    monkeypatch.delenv('USAGE_MANAGER_COLLECTION', raising=False)
    passwords = iter(['new-admin-password-2026'] * 2)
    monkeypatch.setattr(standalone.getpass, 'getpass', lambda prompt: next(passwords))
    return home


def test_setup_shares_persistent_database_and_collection_without_exports(installation, monkeypatch):
    assert not config.collection_enabled()
    standalone.main(['setup'])
    path = config.database_path()
    assert path == installation / 'plugin-data/hermes-usage-manager/usage.sqlite3'
    assert context().db_path == str(path.resolve())
    assert storage_path() == path
    assert config.collection_enabled()
    auth = installation / 'usage-manager-data/standalone-auth.json'
    before = auth.read_bytes()
    with Store(path).transaction() as connection:
        connection.execute("INSERT INTO departments(id, name) VALUES('retained', 'Keep me')")
    monkeypatch.setattr(standalone.getpass, 'getpass', lambda prompt: pytest.fail('Repeated setup must not ask for a password'))
    standalone.main(['setup'])
    assert auth.read_bytes() == before
    with Store(path).read() as connection:
        assert connection.execute("SELECT name FROM departments WHERE id='retained'").fetchone()[0] == 'Keep me'
    served = []
    monkeypatch.setitem(sys.modules, 'uvicorn', SimpleNamespace(run=lambda app, **kwargs: served.append((app, kwargs))))
    standalone.main(['serve'])
    assert served[0][0].state.hum_runtime.store.path == path.resolve()
    assert served[0][1]['host'] == '127.0.0.1'
    monkeypatch.setenv('USAGE_MANAGER_COLLECTION', '0')
    assert not config.collection_enabled()
    override = installation / 'custom/usage.sqlite3'
    monkeypatch.setenv('USAGE_MANAGER_DB_PATH', str(override))
    assert config.database_path() == override
    with pytest.raises(SystemExit):
        standalone.main(['setup'])
    assert json.loads(config.settings_path().read_text())['database'] == str(path)


def test_setup_systemd_is_explicit_repeatable_and_reports_failure(installation, monkeypatch):
    monkeypatch.setattr(standalone.sys, 'platform', 'linux')
    calls = []
    monkeypatch.setattr(standalone.subprocess, 'run', lambda args, **kwargs: calls.append(args))
    standalone.main(['setup', '--start-service'])
    unit = standalone.Path.home() / '.config/systemd/user/hermes-usage-manager.service'
    before = unit.read_bytes()
    assert 'HERMES_HOME=' in before.decode()
    assert calls == [['systemctl', '--user', 'daemon-reload'], ['systemctl', '--user', 'enable', '--now', 'hermes-usage-manager.service']]
    standalone.main(['setup', '--start-service'])
    assert unit.read_bytes() == before
    unit.write_text('custom service', encoding='utf-8')
    calls.clear()
    with pytest.raises(SystemExit):
        standalone.main(['setup', '--start-service'])
    assert unit.read_text() == 'custom service'
    assert not calls


def test_invalid_settings_fail_closed(installation):
    standalone.main(['setup'])
    config.settings_path().write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError):
        config.collection_enabled()


def test_systemd_failure_keeps_setup_and_can_be_retried(installation, monkeypatch, capsys):
    monkeypatch.setattr(standalone.sys, 'platform', 'linux')
    def fail(args, **kwargs):
        raise standalone.subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(standalone.subprocess, 'run', fail)
    with pytest.raises(SystemExit) as error:
        standalone.main(['setup', '--start-service'])
    assert error.value.code == 1
    assert 'systemd' in capsys.readouterr().err
    assert config.database_path().is_file()
    assert config.collection_enabled()
    monkeypatch.setattr(standalone.subprocess, 'run', lambda *args, **kwargs: None)
    standalone.main(['setup', '--start-service'])


def test_core_database_override_rejected_before_setup(installation, monkeypatch):
    core = installation / 'state.db'
    monkeypatch.setenv('USAGE_MANAGER_DB_PATH', str(core))
    with pytest.raises(SystemExit):
        standalone.main(['setup'])
    assert not core.exists()
    assert not config.settings_path().exists()
