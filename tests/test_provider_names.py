from backend.adapters.providers import configured_provider, endpoint, resolve_provider
from backend.adapters import providers


def test_provider_uses_matching_named_endpoint_and_preserves_explicit_provider():
    config = {'model': {'provider': 'ofox', 'base_url': 'https://api.ofox.io/v1'},
              'providers': {'ofox': {'base_url': 'https://api.ofox.io/v1'}, 'other': {'base_url': 'https://other.test/v1'}}}
    assert configured_provider('custom', 'https://api.ofox.io/v1/', config) == 'ofox'
    assert configured_provider('auto', 'https://other.test/v1', config) == 'other'
    assert configured_provider('deepseek', 'https://api.ofox.io/v1', config) == 'deepseek'
    assert configured_provider('custom', 'https://api.ofox.io/different', config) == 'custom'
    assert configured_provider('custom', None, config) == 'custom'
    assert endpoint('https://user:private@api.ofox.io/v1') is None


def test_ambiguous_aliases_do_not_guess_and_selected_model_requires_endpoint_match():
    config = {'providers': {'a': {'base_url': 'https://same.test/v1'}, 'b': {'base_url': 'https://same.test/v1'}},
              'model': {'provider': 'ofox', 'base_url': 'https://different.test/v1'}}
    assert configured_provider('custom', 'https://same.test/v1', config) == 'custom'
    config['model'] = {'provider': 'b', 'base_url': 'https://same.test/v1'}
    assert configured_provider('custom', 'https://same.test/v1', config) == 'b'


def test_missing_config_falls_back_without_throwing(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, 'hermes_home', lambda: tmp_path)
    assert resolve_provider('custom', 'https://api.ofox.io/v1') == 'custom'
    assert resolve_provider('named-provider', None) == 'named-provider'


def test_normalized_provider_matches_its_price_without_storing_endpoint(tmp_path, monkeypatch):
    from backend.adapters.hooks import HookContext, Normalizer
    from backend.db import Store
    from backend.events import ingest_model
    from backend.admin import save_price
    from backend.schemas import PriceBody
    from backend.security import Principal
    monkeypatch.setattr(providers, 'hermes_home', lambda: tmp_path)
    (tmp_path / 'config.yaml').write_text('{}')
    monkeypatch.setattr(providers, 'provider_config', lambda *args: {'providers': {'ofox': {'base_url': 'https://api.ofox.io/v1'}}})
    scope = HookContext('instance', 'profile', str(tmp_path / 'usage.sqlite3'))
    event = Normalizer().normalize('post_api_request', {
        'session_id': 's1', 'api_request_id': 'r1', 'provider': 'custom', 'model': 'model-a',
        'base_url': 'https://api.ofox.io/v1?api_key=DO_NOT_STORE',
        'started_at': 1791993600.0, 'ended_at': 1791993601.0,
        'usage': {'input_tokens': 100, 'cache_read_tokens': 0, 'cache_write_tokens': 0, 'prompt_tokens': 100, 'output_tokens': 20},
    }, scope)
    assert event.provider == 'ofox'
    assert 'DO_NOT_STORE' not in event.model_dump_json() and 'api.ofox.io' not in event.model_dump_json()
    store = Store(scope.db_path)
    with store.transaction() as c:
        save_price(c, Principal('admin', 'admin'), PriceBody(provider='ofox', model='model-a', input='2', cached='0.5', output='4', valid_from='2026-10-01'))
        assert ingest_model(c, event)
        assert c.execute('SELECT cost_micro_usd FROM llm_requests').fetchone()[0] == 280
