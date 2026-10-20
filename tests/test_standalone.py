import json
import os
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import api
from backend.db import Store
from backend.standalone import COOKIE, ROOT, canonical_origin, create_app, initialize_auth, main, read_auth, service_text

PASSWORD = 'isolated-test-password-2026'
PREFIX = '/api/plugins/hermes-usage-manager'


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / 'credentials' / 'auth.json'
    initialize_auth(path, PASSWORD)
    database = tmp_path / 'usage.sqlite3'
    application = create_app(path, database, 'http://testserver', allow_http=True)
    with TestClient(application) as client:
        yield client, application, path, database


def login(client, origin='http://testserver'):
    result = client.post('/api/auth/login', headers={'Origin': origin}, json={'password': PASSWORD})
    assert result.status_code == 200, result.text
    return result.json()['csrf']


def test_credentials_private_hashed_and_never_overwritten(tmp_path):
    path = tmp_path / 'private' / 'auth.json'
    initialize_auth(path, PASSWORD)
    before = path.read_bytes()
    assert PASSWORD not in before.decode()
    assert len(read_auth(path)[0]) == 16
    with pytest.raises(FileExistsError):
        initialize_auth(path, PASSWORD + '-new')
    assert path.read_bytes() == before
    if os.name != 'nt':
        assert path.stat().st_mode & 0o777 == 0o600
        os.chmod(path, 0o644)
        with pytest.raises(ValueError):
            read_auth(path)


@pytest.mark.parametrize('password', ['short', ' ' * 20, 'x' * 257])
def test_weak_or_oversized_credentials_rejected(tmp_path, password):
    with pytest.raises(ValueError):
        initialize_auth(tmp_path / 'auth.json', password)


def test_auth_paths_fail_closed(tmp_path):
    with pytest.raises(ValueError):
        initialize_auth(Path('relative.json'), PASSWORD)
    with pytest.raises(ValueError):
        initialize_auth(ROOT / 'credentials.json', PASSWORD)
    path = tmp_path / 'auth.json'
    path.write_text(json.dumps({'format': 1, 'salt': '', 'password_hash': ''}))
    if os.name != 'nt':
        os.chmod(path, 0o600)
    with pytest.raises(ValueError):
        read_auth(path)


def test_all_business_and_health_routes_require_cookie_not_headers(setup):
    client, application, _, _ = setup
    for path in ('/health', '/filters', '/people/users', '/models/prices', '/audit/access-logs', '/exports/requests.csv'):
        result = client.get(PREFIX + path, headers={'x-hum-mock-role': 'admin', 'Authorization': 'Bearer invented'})
        assert result.status_code == 401
    assert client.get('/api/auth/session').status_code == 401
    assert client.get('/').status_code == 200
    assert client.get('/standalone-assets/app.js').status_code == 200
    assert client.get('/dashboard-plugins/hermes-usage-manager/dist/index.js').status_code == 404
    assert client.get('/docs').status_code == 404
    assert not application.state.hum_sessions.values


def test_authenticated_live_api_and_shared_database(setup, monkeypatch):
    client, _, _, database = setup
    monkeypatch.delenv('USAGE_MANAGER_TRUST_DASHBOARD_ADMIN', raising=False)
    csrf = login(client)
    assert client.get(PREFIX + '/health').json()['data_source'] == 'live'
    assert client.get(PREFIX + '/filters').json()['meta']['data_source'] == 'live'
    result = client.post(PREFIX + '/people/departments', json={'name': '独立端口测试'}, headers={'Origin': 'http://testserver', 'x-hum-csrf': csrf})
    assert result.status_code == 200, result.text
    assert result.json()['meta']['data_source'] == 'live'
    with Store(database).read() as connection:
        assert connection.execute('SELECT name FROM departments WHERE name=?', ('独立端口测试',)).fetchone()
    cookie = client.cookies[COOKIE]
    assert cookie not in client.get('/api/auth/session').text


def test_origin_and_csrf_enforced_for_login_mutations_and_logout(setup):
    client, _, _, _ = setup
    assert client.post('/api/auth/login', json={'password': PASSWORD}).status_code == 403
    assert client.post('/api/auth/login', headers={'Origin': 'http://evil.invalid'}, json={'password': PASSWORD}).status_code == 403
    csrf = login(client)
    for headers in ({}, {'Origin': 'http://evil.invalid', 'x-hum-csrf': csrf}, {'Origin': 'http://testserver'}, {'Origin': 'http://testserver', 'x-hum-csrf': 'wrong'}):
        assert client.post(PREFIX + '/people/departments', headers=headers, json={'name': 'denied'}).status_code == 403
        assert client.post('/api/auth/logout', headers=headers).status_code == 403
    assert client.get(PREFIX + '/health', headers={'Host': 'evil.invalid'}).status_code == 400


def test_login_rate_limit_expiry_and_retry(setup):
    client, application, _, _ = setup
    for _ in range(5):
        assert client.post('/api/auth/login', headers={'Origin': 'http://testserver'}, json={'password': 'wrong'}).status_code == 401
    limited = client.post('/api/auth/login', headers={'Origin': 'http://testserver'}, json={'password': PASSWORD})
    assert limited.status_code == 429
    assert limited.headers['retry-after'] == '60'
    sessions = application.state.hum_sessions
    sessions.failures['testclient'] = [time.monotonic() - 61]
    login(client)


def test_logout_revokes_copied_cookie_and_login_rotates_session(setup):
    client, _, _, _ = setup
    login(client)
    old = client.cookies[COOKIE]
    csrf = login(client)
    rotated = client.cookies[COOKIE]
    assert old != rotated
    assert client.get(PREFIX + '/health', headers={'Cookie': f'{COOKIE}={old}'}).status_code == 401
    result = client.post('/api/auth/logout', headers={'Origin': 'http://testserver', 'x-hum-csrf': csrf})
    assert result.status_code == 200
    assert COOKIE not in client.cookies
    assert client.get(PREFIX + '/health', headers={'Cookie': f'{COOKIE}={rotated}'}).status_code == 401


def test_session_expiry_and_restart_fail_closed(setup):
    client, application, auth, database = setup
    login(client)
    cookie = client.cookies[COOKIE]
    sessions = application.state.hum_sessions
    for key, value in list(sessions.values.items()):
        sessions.values[key] = (time.monotonic() - 1, value[1])
    assert client.get(PREFIX + '/health').status_code == 401
    with TestClient(create_app(auth, database, 'http://testserver', True)) as restarted:
        assert restarted.get(PREFIX + '/health', headers={'Cookie': f'{COOKIE}={cookie}'}).status_code == 401


def test_https_cookie_and_security_headers(setup):
    _, _, auth, database = setup
    with TestClient(create_app(auth, database, 'https://usage.example.com'), base_url='https://usage.example.com') as client:
        response = client.post('/api/auth/login', headers={'Origin': 'https://usage.example.com'}, json={'password': PASSWORD})
        assert response.status_code == 200
        cookie = response.headers['set-cookie']
        assert all(value in cookie for value in ('HttpOnly', 'Secure', 'SameSite=strict', 'Max-Age=28800'))
        for path in ('/', '/standalone-assets/app.js', PREFIX + '/health'):
            response = client.get(path)
            assert response.headers['cache-control'] == 'no-store'
            assert "frame-ancestors 'none'" in response.headers['content-security-policy']
            assert response.headers['x-content-type-options'] == 'nosniff'


@pytest.mark.parametrize('url', ['ftp://usage.example.com', 'http://user:pass@usage.example.com', 'https://usage.example.com/path', 'https://usage.example.com?key=secret', 'https://usage.example.com/#hash', ''])
def test_invalid_public_origins_rejected(url):
    with pytest.raises(ValueError):
        canonical_origin(url)


def test_remote_http_requires_explicit_test_override_and_assets_are_required(setup, tmp_path):
    _, _, auth, database = setup
    with pytest.raises(ValueError, match='HTTPS'):
        create_app(auth, database, 'http://usage.example.com')
    with pytest.raises(ValueError, match='assets'):
        create_app(auth, database, 'http://localhost:9120', assets=tmp_path / 'missing')


def test_native_auth_is_not_replaced_by_standalone_override(setup, monkeypatch):
    client, _, _, _ = setup
    login(client)
    monkeypatch.delenv('USAGE_MANAGER_TRUST_DASHBOARD_ADMIN', raising=False)
    native = FastAPI()
    native.dependency_overrides[api.get_runtime] = lambda: setup[1].state.hum_runtime
    native.include_router(api.router, prefix=PREFIX)
    with TestClient(native) as other:
        assert other.get(PREFIX + '/people/users', headers={'Cookie': f'{COOKIE}={client.cookies[COOKIE]}'}).status_code == 403


def test_cli_requires_explicit_database_and_remote_origin(monkeypatch):
    monkeypatch.delenv('USAGE_MANAGER_DB_PATH', raising=False)
    with pytest.raises(SystemExit) as error:
        main(['serve'])
    assert error.value.code == 1
    monkeypatch.setenv('USAGE_MANAGER_DB_PATH', '/tmp/standalone-test/usage.sqlite3')
    with pytest.raises(SystemExit) as error:
        main(['serve', '--host', '0.0.0.0'])
    assert error.value.code == 1


def test_systemd_unit_has_no_secrets_and_quotes_paths_safely(tmp_path):
    text = service_text(tmp_path / 'auth.json', tmp_path / 'data with space%/usage.sqlite3', '127.0.0.1', 9120, 'http://127.0.0.1:9120')
    assert 'data with space%%' in text
    assert 'USAGE_MANAGER_DB_PATH=' in text
    assert 'UMask=0077' in text
    assert 'WorkingDirectory=' not in text
    assert PASSWORD not in text
    assert 'hermes-gateway' not in text
    assert '--allow-http' not in text
    with pytest.raises(ValueError):
        service_text('auth\nmalicious', tmp_path / 'usage.sqlite3', '127.0.0.1', 9120, 'http://127.0.0.1:9120')


def test_service_cli_writes_only_own_new_unit_and_refuses_overwrite(setup, monkeypatch, tmp_path):
    from backend import standalone
    _, _, auth, database = setup
    home = tmp_path / 'home'
    monkeypatch.setattr(standalone.Path, 'home', lambda: home)
    monkeypatch.setattr(standalone.sys, 'platform', 'linux')
    monkeypatch.setenv('USAGE_MANAGER_DB_PATH', str(database))
    main(['service', '--auth-file', str(auth)])
    unit = home / '.config/systemd/user/hermes-usage-manager.service'
    before = unit.read_bytes()
    assert 'hermes-gateway' not in before.decode()
    with pytest.raises(SystemExit) as error:
        main(['service', '--auth-file', str(auth)])
    assert error.value.code == 1
    assert unit.read_bytes() == before


def test_init_cli_password_confirmation_and_no_secret_in_output(tmp_path, monkeypatch, capsys):
    from backend import standalone
    path = tmp_path / 'private' / 'auth.json'
    passwords = iter([PASSWORD, 'not matching'])
    monkeypatch.setattr(standalone.getpass, 'getpass', lambda prompt: next(passwords))
    with pytest.raises(SystemExit):
        main(['init', '--auth-file', str(path)])
    assert not path.exists()
    passwords = iter([PASSWORD, PASSWORD])
    main(['init', '--auth-file', str(path)])
    assert path.exists()
    captured = capsys.readouterr()
    assert PASSWORD not in captured.out + captured.err


def test_untrusted_forwarded_headers_do_not_control_origin_or_identity(setup):
    client, _, _, _ = setup
    headers = {'Origin': 'http://evil.invalid', 'X-Forwarded-Host': 'testserver', 'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '127.0.0.1'}
    assert client.post('/api/auth/login', json={'password': PASSWORD}, headers=headers).status_code == 403
    assert client.get(PREFIX + '/people/users', headers=headers).status_code == 401


def test_login_validation_does_not_echo_password(setup):
    client, _, _, _ = setup
    oversized = 'sensitive-password-' * 50
    response = client.post('/api/auth/login', json={'password': oversized}, headers={'Origin': 'http://testserver'})
    assert response.status_code == 422
    assert 'sensitive-password' not in response.text
    assert 'input' not in response.text


def test_standalone_refuses_core_database_before_writing(setup, tmp_path):
    _, _, auth, _ = setup
    core = tmp_path / 'state.db'
    with pytest.raises(ValueError, match='core state.db'):
        create_app(auth, core, 'http://localhost:9120')
    assert not core.exists()
