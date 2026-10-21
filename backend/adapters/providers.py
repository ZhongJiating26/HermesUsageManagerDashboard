"""Resolve Hermes generic transport names using matching local provider config."""
import re
from functools import lru_cache
from urllib.parse import urlsplit

from ..config import hermes_home


def endpoint(value):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            return None
        return url.scheme, url.hostname.lower(), url.port or (443 if url.scheme == 'https' else 80), url.path.rstrip('/')
    except ValueError:
        return None


def generic(name):
    return name in ('auto', 'custom') or name.startswith('custom:')


def alias(name):
    return isinstance(name, str) and 0 < len(name) <= 100 and not generic(name) and '://' not in name and not re.search(r'\s|[\x00-\x1f]', name)


def configured_provider(provider, base_url, config):
    if not generic(provider) or not isinstance(config, dict):
        return provider
    target = endpoint(base_url)
    if target is None:
        return provider
    candidates = set()
    providers = config.get('providers', {})
    if isinstance(providers, dict):
        for name, item in providers.items():
            if alias(name) and isinstance(item, dict) and endpoint(item.get('base_url')) == target:
                candidates.add(name)
    custom = config.get('custom_providers', [])
    if isinstance(custom, list):
        for item in custom:
            if isinstance(item, dict) and alias(item.get('name')) and endpoint(item.get('base_url')) == target:
                candidates.add(item['name'])
    model = config.get('model', {})
    if isinstance(model, dict):
        selected = model.get('provider')
        if alias(selected) and endpoint(model.get('base_url')) == target:
            return selected
    return next(iter(candidates)) if len(candidates) == 1 else provider


@lru_cache(maxsize=8)
def provider_config(path, modified, size):
    # Hermes supplies PyYAML. Keep only names/URLs in cache, never credentials.
    import yaml
    with open(path, encoding='utf-8') as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        return {}
    def project(item):
        return {key: item[key] for key in ('name', 'provider', 'base_url') if key in item} if isinstance(item, dict) else {}
    providers = config.get('providers', {})
    custom = config.get('custom_providers', [])
    return {'model': project(config.get('model')), 'providers': {name: project(item) for name, item in providers.items()} if isinstance(providers, dict) else {}, 'custom_providers': [project(item) for item in custom] if isinstance(custom, list) else []}


def resolve_provider(provider, base_url):
    if not generic(provider):
        return provider
    try:
        path = hermes_home() / 'config.yaml'
        stat = path.stat()
        if stat.st_size > 1024 * 1024:
            return provider
        return configured_provider(provider, base_url, provider_config(str(path), stat.st_mtime_ns, stat.st_size))
    except Exception:
        # Unknown/unreadable configuration must not interrupt model execution.
        return provider
