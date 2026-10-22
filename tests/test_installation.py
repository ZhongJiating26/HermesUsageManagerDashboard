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
    assert calls == [['systemctl', '--user', 'daemon-reload'], ['systemctl', '--user', 'enable', 'hermes-usage-manager.service'], ['systemctl', '--user', 'restart', 'hermes-usage-manager.service'], ['systemctl', '--user', 'is-active', '--quiet', 'hermes-usage-manager.service']]
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


def test_inactive_service_never_reports_success_even_if_enable_succeeds(installation, monkeypatch, capsys):
    monkeypatch.setattr(standalone.sys, 'platform', 'linux')
    def run(args, **kwargs):
        if 'is-active' in args:
            raise standalone.subprocess.CalledProcessError(3, args)
    monkeypatch.setattr(standalone.subprocess, 'run', run)
    with pytest.raises(SystemExit) as error:
        standalone.main(['setup', '--start-service'])
    captured = capsys.readouterr()
    assert error.value.code == 1
    assert '后台服务已启动' not in captured.out
    assert 'systemd' in captured.err


def test_exact_legacy_unit_is_backed_up_and_repaired_without_resetting_password(installation, monkeypatch):
    monkeypatch.setattr(standalone.sys, 'platform', 'linux')
    monkeypatch.setattr(standalone.subprocess, 'run', lambda *args, **kwargs: None)
    standalone.main(['setup', '--start-service'])
    auth = installation / 'usage-manager-data/standalone-auth.json'
    credentials = auth.read_bytes()
    unit = standalone.Path.home() / '.config/systemd/user/hermes-usage-manager.service'
    legacy = standalone.service_text(auth, config.database_path(), '127.0.0.1', 9120, 'http://127.0.0.1:9120', _legacy=True)
    unit.write_text(legacy, encoding='utf-8')
    monkeypatch.setattr(standalone.getpass, 'getpass', lambda prompt: pytest.fail('Do not reset existing credentials'))
    standalone.main(['setup', '--start-service'])
    assert 'WorkingDirectory=' not in unit.read_text()
    backups = list(unit.parent.glob('hermes-usage-manager.service.before-fix-*'))
    assert len(backups) == 1
    assert backups[0].read_text(encoding='utf-8') == legacy
    assert auth.read_bytes() == credentials


def test_direct_ip_setup_upgrades_own_loopback_unit_and_keeps_database_and_password(installation, monkeypatch):
    monkeypatch.setattr(standalone.sys, 'platform', 'linux')
    monkeypatch.setattr(standalone.subprocess, 'run', lambda *args, **kwargs: None)
    standalone.main(['setup', '--start-service'])
    database = config.database_path()
    auth = installation / 'usage-manager-data/standalone-auth.json'
    password_record = auth.read_bytes()
    standalone.main(['setup', '--start-service', '--host', '0.0.0.0', '--allow-http'])
    unit = standalone.Path.home() / '.config/systemd/user/hermes-usage-manager.service'
    text = unit.read_text()
    assert '"--host" "0.0.0.0"' in text
    assert '"--allow-http"' in text
    assert '--public-url' not in text
    assert auth.read_bytes() == password_record
    assert config.database_path() == database
    assert list(unit.parent.glob('hermes-usage-manager.service.before-fix-*'))


@pytest.mark.parametrize('host', ['127.0.0.1', '0.0.0.0'])
def test_prompt_changes_generated_service_port_and_retains_data(installation, monkeypatch, host):
    monkeypatch.setattr(standalone.sys, 'platform', 'linux')
    monkeypatch.setattr(standalone.subprocess, 'run', lambda *args, **kwargs: None)
    options = ['setup', '--start-service', '--host', host, '--allow-http']
    standalone.main(options)
    auth = installation / 'usage-manager-data/standalone-auth.json'
    credentials = auth.read_bytes()
    with Store(config.database_path()).transaction() as connection:
        connection.execute("INSERT INTO departments(id, name) VALUES('keep-port', 'Retained')")
    unit = standalone.Path.home() / '.config/systemd/user/hermes-usage-manager.service'
    original = unit.read_text(encoding='utf-8')
    values = iter(['0', '65536', '-1', 'abc', '9.5', '9200'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(values))
    standalone.main(options + ['--prompt-port'])
    assert '"--port" "9200"' in unit.read_text(encoding='utf-8')
    if host == '127.0.0.1':
        assert 'http://127.0.0.1:9200' in unit.read_text(encoding='utf-8')
    backup, = unit.parent.glob('hermes-usage-manager.service.before-fix-*')
    assert backup.read_text(encoding='utf-8') == original
    prompts = []
    monkeypatch.setattr('builtins.input', lambda prompt: prompts.append(prompt) or '')
    standalone.main(options + ['--prompt-port'])
    assert '9200' in prompts[0]
    assert '"--port" "9200"' in unit.read_text(encoding='utf-8')
    assert len(list(unit.parent.glob('hermes-usage-manager.service.before-fix-*'))) == 1
    assert auth.read_bytes() == credentials
    with Store(config.database_path()).read() as connection:
        assert connection.execute("SELECT name FROM departments WHERE id='keep-port'").fetchone()[0] == 'Retained'


def test_port_prompt_default_explicit_override_and_eof(installation, monkeypatch):
    prompts = []
    monkeypatch.setattr('builtins.input', lambda prompt: prompts.append(prompt) or '')
    standalone.main(['setup', '--prompt-port'])
    assert '9120' in prompts[0]
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('Explicit --port must skip prompt'))
    standalone.main(['setup', '--prompt-port', '--port', '65535'])
    for port in ('0', '65536'):
        with pytest.raises(SystemExit):
            standalone.main(['setup', '--prompt-port', '--port', port])
    def no_input(prompt):
        raise EOFError
    monkeypatch.setattr('builtins.input', no_input)
    with pytest.raises(SystemExit):
        standalone.main(['setup', '--prompt-port'])


def test_port_change_does_not_overwrite_custom_unit(installation, monkeypatch):
    monkeypatch.setattr(standalone.sys, 'platform', 'linux')
    calls = []
    monkeypatch.setattr(standalone.subprocess, 'run', lambda args, **kwargs: calls.append(args))
    options = ['setup', '--start-service', '--host', '0.0.0.0', '--allow-http']
    standalone.main(options)
    unit = standalone.Path.home() / '.config/systemd/user/hermes-usage-manager.service'
    custom = unit.read_text(encoding='utf-8') + '\n# Customized by administrator\n'
    unit.write_text(custom, encoding='utf-8')
    calls.clear()
    monkeypatch.setattr('builtins.input', lambda prompt: '9200')
    with pytest.raises(SystemExit):
        standalone.main(options + ['--prompt-port'])
    assert unit.read_text(encoding='utf-8') == custom
    assert not calls
    assert not list(unit.parent.glob('hermes-usage-manager.service.before-fix-*'))
