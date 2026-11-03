"""Opt this plugin into default-branch updates without changing other plugins."""
import argparse
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile

NAME = 'hermes-usage-manager'
SOURCES = {
    'https://gitee.com/ZhongJiating26/HermesUsageManagerDashboard.git',
    'https://github.com/ZhongJiating26/HermesUsageManagerDashboard.git',
}


def unpin(home):
    path = Path(home) / 'plugins/.install-metadata.json'
    if not path.exists():
        return None
    if path.is_symlink():
        raise ValueError('Refusing symlinked install metadata')
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > 1024 * 1024:
        raise ValueError('Invalid install metadata file')
    if os.name != 'nt' and (before.st_uid != os.getuid() or before.st_mode & 0o022):
        raise ValueError('Unsafe install metadata ownership or permissions')
    original = path.read_bytes()
    data = json.loads(original)
    if not isinstance(data, dict):
        raise ValueError('Invalid install metadata format')
    entry = data.get(NAME)
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise ValueError('Invalid plugin install record')
    if entry.get('pinned') is not True:
        return None
    if entry.get('source') not in SOURCES:
        raise ValueError('Refusing to unpin an unrecognized plugin source')
    # Keep the installed revision for auditing; only change update policy.
    entry['pinned'] = False
    backup = path.with_name(path.name + '.before-hum-unpin-' + secrets.token_hex(6))
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.hum-unpin-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        current = path.stat()
        if (current.st_ino, current.st_size, current.st_mtime_ns) != (before.st_ino, before.st_size, before.st_mtime_ns):
            raise ValueError('Install metadata changed concurrently; retry after installation finishes')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', help='Hermes home; defaults to the active profile')
    args = parser.parse_args()
    if args.home:
        home = Path(args.home).expanduser()
    else:
        try:
            from hermes_constants import get_hermes_home
            home = get_hermes_home()
        except ImportError:
            home = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes')).expanduser()
    backup = unpin(home)
    if backup:
        print(f'已解除本插件的提交锁定，后续普通安装将更新默认分支。安装记录备份：{backup}')
    else:
        print('本插件未锁定提交，无需修复。')


if __name__ == '__main__':
    main()
