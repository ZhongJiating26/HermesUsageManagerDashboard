import os

from fastapi import HTTPException

from ..config import database_path, settings


def storage_path():
    if os.environ.get('USAGE_MANAGER_DB_PATH') or settings().get('database'):
        return database_path()
    try:
        from plugins.plugin_storage import plugin_data_dir
    except ImportError as error:
        raise RuntimeError('Hermes storage unavailable; run the plugin installation setup') from error
    return plugin_data_dir('hermes-usage-manager') / 'usage.sqlite3'


def require_dashboard_admin(request):
    try:
        from hermes_cli.web_server import _require_token
    except ImportError as error:
        raise HTTPException(503, {"code": "HOST_AUTH_UNAVAILABLE", "message": "当前 Hermes 宿主认证适配不可用"}) from error
    _require_token(request)
