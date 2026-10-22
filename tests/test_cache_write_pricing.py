import pytest

from tests.test_m2_sqlite import ADMIN, PREFIX, RANGE, admin, client, db, events, insert, model, price, runtime


def write_event(identifier='write', **overrides):
    return model(identifier, **({'input_total_tokens': 49079, 'cached_input_tokens': 48134,
                                'cache_write_tokens': 942, 'output_tokens': 49,
                                'provider_usage_schema': 'hermes-canonical/source-525dbcad'} | overrides))


def test_write_price_backfills_history_once_with_four_distinct_buckets(runtime, client):
    insert(runtime, write_event())
    response = client.post(PREFIX + '/models/prices', json=price(input='0.1', cached='0.01', output='0.5').model_dump(mode='json'))
    price_id = response.json()['data']['id']
    pending = client.get(PREFIX + '/models/unpriced').json()['data']
    assert pending[0]['reason'] == '缓存写入未定价'
    assert pending[0]['existing_price']['id'] == price_id
    assert pending[0]['existing_price']['cache_write'] is None
    assert client.get(PREFIX + '/requests', params=RANGE).json()['data'][0]['cost'] is None
    body = price(input='0.1', cached='0.01', output='0.5', cache_write='0.125').model_dump(mode='json')
    assert client.patch(PREFIX + '/models/prices/' + price_id, json=body).status_code == 200
    assert client.get(PREFIX + '/models/unpriced').json()['data'] == []
    with runtime.store.read() as connection:
        before = dict(connection.execute('SELECT * FROM llm_requests').fetchone())
        assert (before['uncached_input_tokens'], before['cached_input_tokens'], before['cache_write_tokens'], before['output_tokens']) == (3, 48134, 942, 49)
        assert (before['input_cost_micro_usd'], before['cached_cost_micro_usd'], before['cache_write_cost_micro_usd'], before['output_cost_micro_usd'], before['cost_micro_usd']) == (0, 481, 118, 25, 624)
    detail = client.get(PREFIX + '/requests/' + before['event_key'], params=RANGE).json()['data']
    assert (detail['input'], detail['cached'], detail['cache_write'], detail['output']) == (3, 48134, 942, 49)
    summary = client.get(PREFIX + '/overview/summary', params=RANGE).json()['data']
    assert summary['kpis']['total_tokens'] == 49128
    assert summary['kpis']['cache_write'] == 942
    assert summary['kpis']['cache_write_cost'] == pytest.approx(0.000118)
    assert sum(summary['kpis'][field] for field in ('input', 'cached', 'cache_write', 'output')) == 49128
    assert client.patch(PREFIX + '/models/prices/' + price_id, json=body | {'cache_write': 1}).status_code == 200
    with runtime.store.read() as connection:
        assert dict(connection.execute('SELECT * FROM llm_requests').fetchone()) == before
    insert(runtime, write_event('new-live'))
    with runtime.store.read() as connection:
        assert connection.execute("SELECT cache_write_cost_micro_usd FROM llm_requests WHERE source_event_id='new-live'").fetchone()[0] == 942
    assert client.patch(PREFIX + '/settings', json={'export_enabled': True}).status_code == 200
    exported = client.get(PREFIX + '/exports/requests.csv', params=RANGE)
    assert exported.status_code == 200
    assert 'cache_write' in exported.text.splitlines()[0]


def test_upgrade_legacy_canonical_write_rows_without_repricing_known_costs(runtime):
    insert(runtime, write_event())
    insert(runtime, write_event('untrusted', provider_usage_schema='unknown', pricing_supported=False))
    insert(runtime, model('priced'))
    with runtime.store.transaction() as connection:
        price_id = admin.save_price(connection, ADMIN, price())
        # Reconstruct the original five-migration layout and its merged input bucket.
        connection.execute("UPDATE llm_requests SET uncached_input_tokens=945,pricing_supported=0 WHERE source_event_id='write'")
        connection.execute("DELETE FROM schema_migrations WHERE version='0006_cache_write_pricing'")
        connection.execute('ALTER TABLE model_prices DROP COLUMN cache_write')
        connection.execute('ALTER TABLE llm_requests DROP COLUMN cache_write_cost_micro_usd')
        known = dict(connection.execute("SELECT * FROM llm_requests WHERE source_event_id='priced'").fetchone())
    reopened = db.Store(runtime.store.path)
    with reopened.transaction() as connection:
        migrated = dict(connection.execute("SELECT * FROM llm_requests WHERE source_event_id='write'").fetchone())
        assert migrated['uncached_input_tokens'] == 3
        assert migrated['pricing_supported'] == 1
        assert migrated['cost_micro_usd'] is None
        assert connection.execute("SELECT pricing_supported FROM llm_requests WHERE source_event_id='untrusted'").fetchone()[0] == 0
        admin.save_price(connection, ADMIN, price(cache_write='0.125'), price_id)
        assert connection.execute("SELECT cost_micro_usd FROM llm_requests WHERE source_event_id='write'").fetchone()[0] == 24387
        after = dict(connection.execute("SELECT * FROM llm_requests WHERE source_event_id='priced'").fetchone())
        assert {key: after[key] for key in known} == known
    # Reopening must not subtract the write bucket a second time.
    with db.Store(runtime.store.path).read() as connection:
        assert connection.execute("SELECT uncached_input_tokens FROM llm_requests WHERE source_event_id='write'").fetchone()[0] == 3


def test_missing_write_price_is_unknown_but_explicit_zero_is_known(runtime):
    with runtime.store.transaction() as connection:
        price_id = admin.save_price(connection, ADMIN, price())
        events.ingest_model(connection, write_event())
        assert connection.execute('SELECT cost_micro_usd FROM llm_requests').fetchone()[0] is None
        admin.save_price(connection, ADMIN, price(cache_write='0'), price_id)
        assert connection.execute('SELECT cache_write_cost_micro_usd FROM llm_requests').fetchone()[0] == 0
        assert connection.execute('SELECT cost_micro_usd FROM llm_requests').fetchone()[0] is not None


@pytest.mark.parametrize('rate', [-1, 'NaN', 'Infinity', '0.1234567'])
def test_invalid_write_prices_rejected(runtime, client, rate):
    body = price().model_dump(mode='json') | {'cache_write': rate}
    assert client.post(PREFIX + '/models/prices', json=body).status_code == 422


def test_old_client_does_not_clear_configured_write_price(runtime, client):
    response = client.post(PREFIX + '/models/prices', json=price(cache_write='0.125').model_dump(mode='json'))
    identifier = response.json()['data']['id']
    body = price().model_dump(mode='json')
    del body['cache_write']
    assert client.patch(PREFIX + '/models/prices/' + identifier, json=body).status_code == 200
    configured = client.get(PREFIX + '/models/prices').json()['data']
    assert configured[0]['cache_write'] == 0.125


def test_old_gateway_event_after_migration_can_still_be_backfilled(runtime):
    insert(runtime, write_event())
    with runtime.store.transaction() as connection:
        connection.execute('UPDATE llm_requests SET pricing_supported=0,uncached_input_tokens=945')
        admin.save_price(connection, ADMIN, price(cache_write='0.125'))
        row = connection.execute('SELECT * FROM llm_requests').fetchone()
        assert row['uncached_input_tokens'] == 3
        assert row['pricing_supported'] == 1
        assert row['cost_micro_usd'] == 24387


def test_queued_legacy_canonical_event_uses_new_write_price(runtime):
    with runtime.store.transaction() as connection:
        admin.save_price(connection, ADMIN, price(cache_write='0.125'))
        events.ingest_model(connection, write_event(pricing_supported=False))
        row = connection.execute('SELECT * FROM llm_requests').fetchone()
        assert row['uncached_input_tokens'] == 3
        assert row['pricing_supported'] == 1
        assert row['cost_micro_usd'] == 24387
