import json

import pytest

from tests.test_m2_sqlite import ADMIN, PREFIX, RANGE, admin, client, events, insert, model, price, runtime


def request_rows(runtime):
    with runtime.store.read() as connection:
        return {r['source_event_id']: dict(r) for r in connection.execute('SELECT * FROM llm_requests')}


def test_save_price_backfills_only_eligible_unknown_history(runtime, client):
    insert(runtime, model('eligible'))
    insert(runtime, model('zero', input_total_tokens=0, cached_input_tokens=0, output_tokens=0))
    insert(runtime, model('missing', cached_input_tokens=None))
    insert(runtime, model('unsupported', pricing_supported=False, cache_write_tokens=10))
    insert(runtime, model('different-provider', provider='Other'))
    insert(runtime, model('different-model', model='other-model'))
    insert(runtime, model('before', occurred_at='2026-09-30T23:59:59+08:00'))
    insert(runtime, model('after', occurred_at='2026-10-16T00:00:00+08:00'))
    before = request_rows(runtime)
    response = client.post(PREFIX + '/models/prices', json=price().model_dump(mode='json'))
    assert response.status_code == 200
    price_id = response.json()['data']['id']
    after = request_rows(runtime)
    assert after['eligible']['cost_micro_usd'] == 235
    assert after['zero']['cost_micro_usd'] == 0
    for identifier in ('missing', 'unsupported', 'different-provider', 'different-model', 'before', 'after'):
        assert after[identifier] == before[identifier]
    for identifier in ('eligible', 'zero'):
        assert after[identifier]['price_id'] == price_id
        assert after[identifier]['price_revision_id']
        assert after[identifier]['cost_source'] == 'estimated'
        assert {k: v for k, v in before[identifier].items() if k not in ('price_id', 'price_revision_id', 'cost_micro_usd', 'cost_source', 'input_cost_micro_usd', 'cached_cost_micro_usd', 'output_cost_micro_usd', 'cache_write_cost_micro_usd')} == {k: v for k, v in after[identifier].items() if k not in ('price_id', 'price_revision_id', 'cost_micro_usd', 'cost_source', 'input_cost_micro_usd', 'cached_cost_micro_usd', 'output_cost_micro_usd', 'cache_write_cost_micro_usd')}
    # Editing or re-saving the price never overwrites an already known estimate.
    response = client.patch(PREFIX + '/models/prices/' + price_id, json=price(input='20').model_dump(mode='json'))
    assert response.status_code == 200
    assert request_rows(runtime) == after
    with runtime.store.read() as connection:
        records = [json.loads(r[0]) for r in connection.execute("SELECT result FROM audit_access_logs WHERE action='price.backfill'")]
        assert sorted(r['request_count'] for r in records) == [0, 2]
        assert any(r['revision_id'] == after['eligible']['price_revision_id'] for r in records)
    summary = client.get(PREFIX + '/overview/summary', params=RANGE).json()['data']
    assert summary['kpis']['cost'] == pytest.approx(0.000235)


def test_disabled_price_then_expanded_interval_backfills_unknown_rows(runtime, client):
    insert(runtime, model('earlier', occurred_at='2026-09-01T00:00:00+08:00'))
    insert(runtime, model('today'))
    response = client.post(PREFIX + '/models/prices', json=price(enabled=False).model_dump(mode='json'))
    price_id = response.json()['data']['id']
    assert all(r['cost_micro_usd'] is None for r in request_rows(runtime).values())
    response = client.patch(PREFIX + '/models/prices/' + price_id, json=price().model_dump(mode='json'))
    assert response.status_code == 200
    known = request_rows(runtime)['today']
    assert known['cost_micro_usd'] == 235
    assert request_rows(runtime)['earlier']['cost_micro_usd'] is None
    response = client.patch(PREFIX + '/models/prices/' + price_id, json=price(valid_from='2026-09-01', input='3').model_dump(mode='json'))
    assert response.status_code == 200
    assert request_rows(runtime)['earlier']['cost_micro_usd'] == 305
    assert request_rows(runtime)['today'] == known


def test_backfill_matches_live_rounding_across_batches_and_rolls_back(runtime):
    with runtime.store.transaction() as connection:
        for index in range(1003):
            events.ingest_model(connection, model(str(index), input_total_tokens=2, cached_input_tokens=1, output_tokens=1))
    with pytest.raises(RuntimeError):
        with runtime.store.transaction() as connection:
            admin.save_price(connection, ADMIN, price(input='0.5', cached='0.5', output='0.5'))
            raise RuntimeError('Rollback the price and its backfill together')
    assert all(r['cost_micro_usd'] is None for r in request_rows(runtime).values())
    with runtime.store.transaction() as connection:
        assert connection.execute('SELECT count(*) FROM model_prices').fetchone()[0] == 0
        admin.save_price(connection, ADMIN, price(input='0.5', cached='0.5', output='0.5'))
        events.ingest_model(connection, model('live', input_total_tokens=2, cached_input_tokens=1, output_tokens=1))
    data = request_rows(runtime)
    assert len(data) == 1004
    assert all((r['input_cost_micro_usd'], r['cached_cost_micro_usd'], r['output_cost_micro_usd'], r['cost_micro_usd']) == (1, 1, 1, 3) for r in data.values())


def test_price_write_permissions_still_apply(runtime, client):
    insert(runtime, model())
    for role in ('user', 'department', 'auditor'):
        assert client.post(PREFIX + '/models/prices', headers={'test-role': role}, json=price().model_dump(mode='json')).status_code == 403
    assert request_rows(runtime)['one']['cost_micro_usd'] is None
