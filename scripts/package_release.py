"""Build a reproducible, checked native release candidate without network access."""

import hashlib
import ast
import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME = 'hermes-usage-manager'


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def collect(root):
    plugin = yaml.safe_load((root / 'plugin.yaml').read_text(encoding='utf-8'))
    dashboard = json.loads((root / 'dashboard/manifest.json').read_text(encoding='utf-8'))
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    frontend = json.loads((root / 'frontend/package.json').read_text(encoding='utf-8'))
    versions = {plugin['version'], dashboard['version'], project['version'], frontend['version']}
    if len(versions) != 1 or plugin['name'] != NAME or project['name'] != NAME:
        raise ValueError('Release names or versions disagree')
    version = plugin['version']
    assignments = ast.parse((root / 'backend/adapters/hooks.py').read_text(encoding='utf-8')).body
    declared = next(ast.literal_eval(statement.value) for statement in assignments if isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'HOOKS' for target in statement.targets))
    if plugin.get('provides_hooks') != list(declared):
        raise ValueError('Hook declarations and runtime registrations disagree')
    for path in ('backend/api.py', 'backend/responses.py', 'frontend/src/services/api.ts'):
        if version not in (root / path).read_text(encoding='utf-8'):
            raise ValueError('Runtime version disagrees')
    for inventory in ('release-inputs.json', 'standalone-inputs.json'):
        integrity = json.loads((root / 'build' / inventory).read_text(encoding='utf-8'))
        for category in ('inputs', 'outputs'):
            if not integrity.get(category):
                raise ValueError('Missing build integrity inventory')
            for relative, expected in integrity[category].items():
                path = (root / 'frontend' / relative).resolve()
                if not path.is_relative_to(root.resolve()) or checksum(path.read_bytes()) != expected:
                    raise ValueError('Build inputs or outputs changed; rebuild the plugin')
    metadata = json.loads((root / 'build/plugin-metafile.json').read_text(encoding='utf-8'))
    packages = {'echarts', 'zrender', 'tslib', 'zod'}
    for relative in metadata['inputs']:
        segments = relative.replace('\\', '/').split('/node_modules/')
        if len(segments) > 1 and segments[-1].split('/')[0] not in packages:
            raise ValueError('Unexpected bundled runtime dependency')
    if any(output.get('imports') for path, output in metadata['outputs'].items() if path.endswith('.js')):
        raise ValueError('Unresolved JavaScript imports')
    javascript = (root / 'dashboard/dist/index.js').read_text(encoding='utf-8')
    if '__HERMES_PLUGIN_SDK__' not in javascript or any(marker in javascript for marker in ('react-dom', 'jsx-runtime', 'createRoot', '__SECRET_INTERNALS')):
        raise ValueError('Missing host SDK or bundled React runtime')
    standalone = json.loads((root / 'build/standalone-metafile.json').read_text(encoding='utf-8'))
    standalone_inputs = list(standalone['inputs'])
    for relative in standalone_inputs:
        segments = relative.replace('\\', '/').split('/node_modules/')
        if len(segments) > 1 and segments[-1].split('/')[0] not in packages | {'react', 'react-dom', 'scheduler'}:
            raise ValueError('Unexpected standalone runtime dependency')
    if not any('/react-dom/' in path.replace('\\', '/') for path in standalone_inputs) or not any('/react/' in path.replace('\\', '/') for path in standalone_inputs):
        raise ValueError('Standalone entry must provide its own React runtime')
    if any(output.get('imports') for path, output in standalone['outputs'].items() if path.endswith('.js')):
        raise ValueError('Unresolved standalone JavaScript imports')
    roots = ['plugin.yaml', '__init__.py', 'standalone.py', 'install.sh', 'pyproject.toml', 'README.md', 'CHANGELOG.md']
    paths = [root / name for name in roots]
    for directory in ('dashboard', 'backend', 'docs', 'ops', 'standalone'):
        paths.extend(path for path in (root / directory).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    files = {}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or path.suffix not in {'.py', '.sh', '.sql', '.json', '.js', '.css', '.html', '.ttf', '.txt', '.md', '.yaml', '.toml'} or any(part.startswith('.') for part in Path(relative).parts):
            raise ValueError('Unexpected or sensitive runtime file')
        files[relative] = path.read_bytes()
    for field in ('entry', 'css', 'api'):
        if f'dashboard/{dashboard[field]}' not in files:
            raise ValueError('Missing dashboard runtime entry')
    if not any(name.startswith('backend/migrations/') and name.endswith('.sql') for name in files):
        raise ValueError('Missing migrations')
    if 'ops/manage.py' not in files or 'dashboard/dist/THIRD_PARTY_NOTICES.txt' not in files:
        raise ValueError('Missing operations tool or third-party notices')
    if not all(f'standalone/dist/{name}' in files for name in ('index.html', 'app.js', 'app.css', 'THIRD_PARTY_NOTICES.txt')):
        raise ValueError('Missing standalone runtime or licenses')
    return version, files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-tag', action='store_true', help='Require a clean worktree and v<version> tag at HEAD')
    args = parser.parse_args(argv)
    version, files = collect(ROOT)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True))
    tags = subprocess.check_output(['git', 'tag', '--points-at', 'HEAD'], cwd=ROOT, text=True).splitlines()
    tag = f'v{version}' if f'v{version}' in tags else None
    if args.require_tag and (dirty or not tag):
        raise ValueError('A clean commit and matching v<version> tag are required for publication')
    release = {'format': 1, 'name': NAME, 'version': version, 'source_revision': source, 'source_dirty': dirty, 'source_tag': tag, 'release_status': 'candidate' if dirty or not tag else 'tagged', 'files': {name: checksum(data) for name, data in sorted(files.items())}}
    files['release.json'] = (json.dumps(release, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()
    if len(files) > 2048 or len({name.casefold() for name in files}) != len(files) or sum(map(len, files.values())) > 64 * 1024 * 1024:
        raise ValueError('Release inventory exceeds staging limits')
    output = ROOT / f'build/{NAME}-{version}.zip'
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            member = ZipInfo(f'{NAME}/{name}', (1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            member.compress_type = ZIP_DEFLATED
            archive.writestr(member, data)
    helper = output.with_name(f'{NAME}-{version}-ops.py')
    helper.write_bytes(files['ops/manage.py'])
    checksums = output.with_suffix('.sha256')
    checksums.write_text(''.join(f'{checksum(path.read_bytes())}  {path.name}\n' for path in (output, helper)), encoding='ascii', newline='\n')
    print(f'Release ({release["release_status"]}): {output}\nChecksums: {checksums}\nNode-free operations: {helper}\nSource: {source}; dirty={dirty}; tag={tag}')


if __name__ == '__main__':
    main()
