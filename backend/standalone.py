import argparse
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import api
from .db import Store
from .config import database_path, hermes_home, settings, settings_path
from .security import Principal

ROOT = Path(__file__).resolve().parents[1]
COOKIE = 'hum_session'
SESSION_SECONDS = 8 * 60 * 60


def private_path(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError('An absolute path without symlinks is required')
    if path.resolve().is_relative_to(ROOT):
        raise ValueError('Credentials must be outside the plugin installation')
    return path


def password_digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)


def initialize_auth(path, password):
    path = private_path(path)
    if not 12 <= len(password) <= 256 or not password.strip():
        raise ValueError('Use a password of 12 to 256 characters')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != 'nt' and (path.parent.stat().st_uid != os.getuid() or path.parent.stat().st_mode & 0o077):
        raise ValueError('Credential directory must be owned by you with mode 700')
    salt = secrets.token_bytes(16)
    record = {'format': 1, 'salt': salt.hex(), 'password_hash': password_digest(password, salt).hex()}
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        json.dump(record, output)


def read_auth(path):
    path = private_path(path)
    stat = path.stat()
    if stat.st_size > 4096 or (os.name != 'nt' and (stat.st_uid != os.getuid() or stat.st_mode & 0o077)):
        raise ValueError('Unsafe credential file size, ownership or permissions')
    record = json.loads(path.read_text(encoding='utf-8'))
    salt = bytes.fromhex(record['salt'])
    expected = bytes.fromhex(record['password_hash'])
    if record.get('format') != 1 or len(salt) != 16 or len(expected) != 32:
        raise ValueError('Invalid credential record')
    return salt, expected


def canonical_origin(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
        raise ValueError('Public URL must be an http(s) origin without a path or credentials')
    port = parsed.port
    hostname = f'[{parsed.hostname}]' if ':' in parsed.hostname else parsed.hostname
    suffix = f':{port}' if port and port != (443 if parsed.scheme == 'https' else 80) else ''
    return f'{parsed.scheme}://{hostname}{suffix}'


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class Sessions:
    def __init__(self):
        self.lock = RLock()
        self.values = OrderedDict()
        self.failures = OrderedDict()

    def prune(self):
        current = time.monotonic()
        for key, value in list(self.values.items()):
            if value[0] <= current:
                del self.values[key]
        for key, values in list(self.failures.items()):
            self.failures[key] = [value for value in values if value > current - 60]
            if not self.failures[key]:
                del self.failures[key]

    def lookup(self, token):
        with self.lock:
            self.prune()
            return self.values.get(hashlib.sha256(token.encode()).hexdigest())

    def revoke(self, token):
        with self.lock:
            self.values.pop(hashlib.sha256(token.encode()).hexdigest(), None)


def create_app(auth_file, database, public_url, allow_http=False, assets=None):
    origin = canonical_origin(public_url)
    parsed = urlsplit(origin)
    secure = parsed.scheme == 'https'
    if not secure and parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} and not allow_http:
        raise ValueError('Remote access requires HTTPS; --allow-http is for isolated testing only')
    salt, expected = read_auth(auth_file)
    if Path(database).resolve().name.casefold() == 'state.db':
        raise ValueError('Do not use the Hermes core state.db as a usage database')
    runtime = api.Runtime(Store(database), content_provider=api.HermesSessionContentProvider())
    directory = Path(assets) if assets else ROOT / 'standalone/dist'
    for name in ('index.html', 'app.js', 'app.css'):
        if not (directory / name).is_file():
            raise ValueError('Standalone assets are missing; install the prebuilt release')
    sessions = Sessions()
    application = FastAPI(title='Hermes Usage Manager', docs_url=None, redoc_url=None, openapi_url=None)
    application.state.hum_runtime = runtime
    application.state.hum_sessions = sessions
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=[parsed.hostname])

    def check_origin(request):
        supplied = request.headers.get('origin', '')
        try:
            valid = canonical_origin(supplied) == origin
        except ValueError:
            valid = False
        if not valid:
            raise HTTPException(403, {'code': 'ORIGIN_DENIED', 'message': '请求来源不匹配'})

    def authenticate(request: Request):
        session = sessions.lookup(request.cookies.get(COOKIE, ''))
        if not session:
            raise HTTPException(401, {'code': 'LOGIN_REQUIRED', 'message': '请先登录用量管理'})
        request.state.hum_csrf = session[1]
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            check_origin(request)
            if not hmac.compare_digest(request.headers.get('x-hum-csrf', '').encode(), session[1].encode()):
                raise HTTPException(403, {'code': 'CSRF_DENIED', 'message': '请刷新页面后重试'})
        return Principal('standalone-admin', 'admin')

    @application.middleware('http')
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'"
        return response

    @application.exception_handler(HTTPException)
    async def rejected(request, error):
        return JSONResponse({'error': error.detail}, status_code=error.status_code, headers=error.headers)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse({'error': {'code': 'VALIDATION_ERROR', 'message': '请求参数格式不正确'}}, status_code=422)

    @application.post('/api/auth/login')
    def login(body: LoginBody, request: Request, response: Response):
        check_origin(request)
        address = request.client.host if request.client else 'unknown'
        with sessions.lock:
            sessions.prune()
            failures = sessions.failures.setdefault(address, [])
            if len(failures) >= 5:
                raise HTTPException(429, {'code': 'LOGIN_RATE_LIMIT', 'message': '登录尝试过多，请稍后重试'}, headers={'Retry-After': '60'})
            failures.append(time.monotonic())
            while len(sessions.failures) > 1024:
                sessions.failures.popitem(last=False)
        if not hmac.compare_digest(password_digest(body.password, salt), expected):
            raise HTTPException(401, {'code': 'INVALID_CREDENTIALS', 'message': '密码不正确'})
        with sessions.lock:
            sessions.failures.pop(address, None)
            sessions.revoke(request.cookies.get(COOKIE, ''))
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            sessions.values[hashlib.sha256(token.encode()).hexdigest()] = (time.monotonic() + SESSION_SECONDS, csrf)
            while len(sessions.values) > 256:
                sessions.values.popitem(last=False)
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=secure, samesite='strict')
        return {'authenticated': True, 'csrf': csrf}

    @application.get('/api/auth/session')
    def current_session(request: Request, principal=Depends(authenticate)):
        return {'authenticated': True, 'csrf': request.state.hum_csrf}

    @application.post('/api/auth/logout')
    def logout(request: Request, response: Response, principal=Depends(authenticate)):
        sessions.revoke(request.cookies.get(COOKIE, ''))
        response.delete_cookie(COOKIE, httponly=True, secure=secure, samesite='strict')
        return {'authenticated': False}

    application.dependency_overrides[api.get_principal] = authenticate
    application.dependency_overrides[api.get_runtime] = lambda: runtime
    application.include_router(api.router, prefix='/api/plugins/hermes-usage-manager', dependencies=[Depends(authenticate)])
    application.mount('/standalone-assets', StaticFiles(directory=directory))

    @application.get('/')
    def index():
        return FileResponse(directory / 'index.html')

    return application


def service_text(auth_file, database, host, port, public_url, allow_http=False, *, _legacy=False):
    def quote(value, escape_dollar=False):
        value = str(value)
        if any(character in value for character in ('\n', '\r', '\x00')):
            raise ValueError('Newlines are not allowed in service settings')
        value = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
        return '"' + (value.replace('$', '$$') if escape_dollar else value) + '"'

    command = [sys.executable, ROOT / 'standalone.py', 'serve', '--auth-file', auth_file, '--host', host, '--port', port, '--public-url', public_url]
    if allow_http:
        command.append('--allow-http')
    working_directory = ['WorkingDirectory=' + quote(ROOT)] if _legacy else []
    # All runtime paths are absolute; WorkingDirectory is unnecessary and older
    # systemd versions treat its surrounding quotes as part of a relative path.
    return '\n'.join(['[Unit]', 'Description=Hermes Usage Manager independent web entry', 'After=network.target', '', '[Service]', 'Type=simple', *working_directory, 'Environment=' + quote('USAGE_MANAGER_DB_PATH=' + str(database)), 'Environment=' + quote('HERMES_HOME=' + str(hermes_home())), 'ExecStart=' + ' '.join(quote(value, True) for value in command), 'Restart=on-failure', 'RestartSec=5', 'UMask=0077', 'NoNewPrivileges=true', '', '[Install]', 'WantedBy=default.target', ''])


def setup_installation(args, database, origin):
    """Explicit first-run setup; never run from Hook registration."""
    path = private_path(settings_path())
    existing = settings()
    if existing and (existing.get('database') != str(database) or existing.get('auth_file') != str(args.auth_file)):
        raise ValueError('Existing settings use different paths; keep the original paths or inspect settings.json')
    auth = private_path(args.auth_file)
    if auth.exists():
        read_auth(auth)
        print('保留已有管理员密码。')
    else:
        password = getpass.getpass('设置用量管理管理员密码（至少12字符）: ')
        if password != getpass.getpass('再次输入密码: '):
            raise ValueError('Passwords do not match')
        initialize_auth(auth, password)
    create_app(auth, database, origin, args.allow_http)
    if not existing:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump({'format': 1, 'database': str(database), 'auth_file': str(auth), 'collection': True}, output, indent=2)
    print(f'数据库：{database}\n配置：{path}\n访问地址：{origin}')
    print('元数据采集配置已保存；请按原运行方式重启 Gateway，让插件加载配置。')
    if args.start_service:
        if sys.platform != 'linux':
            raise ValueError('--start-service requires Linux user systemd')
        unit = private_path(Path.home() / '.config/systemd/user/hermes-usage-manager.service')
        text = service_text(auth, database, args.host, args.port, origin, args.allow_http)
        unit.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if unit.exists():
            previous = unit.read_text(encoding='utf-8')
            legacy = service_text(auth, database, args.host, args.port, origin, args.allow_http, _legacy=True)
            if previous == legacy:
                backup = unit.with_name(unit.name + '.before-fix-' + secrets.token_hex(4))
                descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
                    output.write(previous)
                unit.write_text(text, encoding='utf-8', newline='\n')
                print(f'已修复旧版服务配置，原文件保存在：{backup}')
            elif previous != text:
                raise ValueError('Existing service settings differ; inspect the existing unit before changing it')
        else:
            descriptor = os.open(unit, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
                output.write(text)
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', '--user', 'enable', '--now', 'hermes-usage-manager.service'], check=True)
        subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'hermes-usage-manager.service'], check=True)
        print('用量管理后台服务已启动。')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Hermes Usage Manager independent web entry')
    parser.add_argument('action', choices=['init', 'serve', 'service', 'setup'])
    parser.add_argument('--auth-file')
    parser.add_argument('--start-service', action='store_true', help='With setup, create and start the Linux user service')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9120)
    parser.add_argument('--public-url')
    parser.add_argument('--allow-http', action='store_true', help='Allow remote plain HTTP for isolated testing only')
    args = parser.parse_args(argv)
    try:
        if args.start_service and args.action != 'setup':
            raise ValueError('--start-service is only supported with setup')
        args.auth_file = args.auth_file or settings().get('auth_file') or str(hermes_home() / 'usage-manager-data/standalone-auth.json')
        if args.action == 'init':
            password = getpass.getpass('设置用量管理管理员密码（至少12字符）: ')
            if password != getpass.getpass('再次输入密码: '):
                raise ValueError('Passwords do not match')
            initialize_auth(args.auth_file, password)
            print('Credentials initialized; no services or network ports were started.')
            return
        database = database_path()
        if not 1 <= args.port <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        if args.host not in {'127.0.0.1', 'localhost', '::1'} and not args.public_url:
            raise ValueError('Remote binding requires an explicit --public-url')
        if args.action == 'setup':
            origin = canonical_origin(args.public_url or f'http://{args.host if args.host != "::1" else "[::1]"}:{args.port}')
            setup_installation(args, database, origin)
            return
        application = create_app(args.auth_file, database, args.public_url or f'http://{args.host if args.host != "::1" else "[::1]"}:{args.port}', args.allow_http)
        if args.action == 'service':
            if sys.platform != 'linux':
                raise ValueError('User systemd service generation requires Linux')
            path = private_path(Path.home() / '.config/systemd/user/hermes-usage-manager.service')
            text = service_text(args.auth_file, database, args.host, args.port, args.public_url or f'http://{args.host if args.host != "::1" else "[::1]"}:{args.port}', args.allow_http)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                output.write(text)
            print('Created hermes-usage-manager.service; no services were started. Run:\nsystemctl --user daemon-reload\nsystemctl --user enable --now hermes-usage-manager.service')
            return
        import uvicorn
        uvicorn.run(application, host=args.host, port=args.port, workers=1, proxy_headers=False, access_log=False)
    except FileExistsError:
        parser.exit(1, 'Existing credentials or service unit are not overwritten; preserve and inspect the existing file.\n')
    except subprocess.CalledProcessError:
        parser.exit(1, '配置已保留，但 systemd 启动失败。请检查 systemctl --user status hermes-usage-manager.service；也可运行 standalone.py serve 前台启动。\n')
    except (ValueError, OSError, KeyError, ImportError, sqlite3.Error) as error:
        parser.exit(1, f'Standalone initialization/start failed ({type(error).__name__}). Check credentials, private paths, database, assets and origin settings.\n')
