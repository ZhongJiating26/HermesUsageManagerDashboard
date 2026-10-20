"""Profile-local installation settings shared by Hooks and both web entries."""

import json
import os
from pathlib import Path


def hermes_home():
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        return Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes')).expanduser().resolve()
    return get_hermes_home().expanduser().resolve()


def settings_path():
    return hermes_home() / 'plugin-data/hermes-usage-manager/settings.json'


def settings():
    path = settings_path()
    if not path.exists():
        return {}
    if path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError('Invalid usage manager settings file')
    if os.name != 'nt' and (path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077):
        raise ValueError('Usage manager settings must be private')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or value.get('format') != 1:
        raise ValueError('Invalid usage manager settings format')
    return value


def database_path():
    configured = os.environ.get('USAGE_MANAGER_DB_PATH') or settings().get('database')
    path = Path(configured).expanduser() if configured else hermes_home() / 'plugin-data/hermes-usage-manager/usage.sqlite3'
    if not path.is_absolute() or path.name.casefold() == 'state.db':
        raise ValueError('Use an absolute plugin database path, never Hermes state.db')
    return path


def collection_enabled():
    if 'USAGE_MANAGER_COLLECTION' in os.environ:
        return os.environ['USAGE_MANAGER_COLLECTION'] == '1'
    return settings().get('collection') is True
