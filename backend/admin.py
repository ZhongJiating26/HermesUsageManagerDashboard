import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from .db import now
from .events import estimate_costs
from .queries import rows
from .schemas import price_period


def audit(connection, principal, action, target, result="ok"):
    connection.execute("INSERT INTO audit_access_logs VALUES(?,?,?,?,?,?,?,?)", (uuid4().hex, principal.id, action, action.split('.')[0], target, now(), result, uuid4().hex))


def save_price(connection, principal, body, price_id=""):
    zone = json.loads(connection.execute("SELECT value_json FROM plugin_settings WHERE key='timezone'").fetchone()[0])
    start, end = price_period(body, zone)
    if price_id and not connection.execute("SELECT 1 FROM model_prices WHERE id=?", (price_id,)).fetchone():
        raise HTTPException(404, "价格配置不存在")
    if price_id and 'cache_write' not in body.model_fields_set:
        previous = connection.execute('SELECT cache_write FROM model_prices WHERE id=?', (price_id,)).fetchone()[0]
        body = body.model_copy(update={'cache_write': Decimal(previous) if previous is not None else None})
    overlap = connection.execute("SELECT id FROM model_prices WHERE provider=? AND model=? AND enabled=1 AND id<>? AND starts_at<coalesce(?,'9999') AND coalesce(ends_at,'9999')>? LIMIT 1", (body.provider, body.model, price_id, end, start)).fetchone()
    if body.enabled and overlap:
        raise HTTPException(409, "同一提供商和模型的启用价格区间不能重叠")
    price_id = price_id or f"price-{uuid4().hex}"
    values = (price_id, body.provider, body.model, str(body.input), str(body.cached), str(body.output), str(body.valid_from), str(body.valid_to) if body.valid_to else None, start, end, int(body.enabled), str(body.cache_write) if body.cache_write is not None else None)
    connection.execute("INSERT INTO model_prices(id,provider,model,input,cached,output,valid_from,valid_to,starts_at,ends_at,enabled,cache_write) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,model=excluded.model,input=excluded.input,cached=excluded.cached,output=excluded.output,valid_from=excluded.valid_from,valid_to=excluded.valid_to,starts_at=excluded.starts_at,ends_at=excluded.ends_at,enabled=excluded.enabled,cache_write=excluded.cache_write", values)
    config = body.model_dump(mode="json")
    revision_id = uuid4().hex
    connection.execute("INSERT INTO price_revisions VALUES(?,?,?,?,?)", (revision_id, price_id, principal.id, now(), json.dumps(config)))
    audit(connection, principal, "price.save", price_id)
    count = backfill_price(connection, price_id, revision_id)
    audit(connection, principal, "price.backfill", price_id, json.dumps({'request_count': count, 'revision_id': revision_id}))
    return price_id


def backfill_price(connection, price_id, revision_id):
    """Fill unknown estimates only, using this revision and its effective dates."""
    price = connection.execute('SELECT * FROM model_prices WHERE id=? AND enabled=1', (price_id,)).fetchone()
    if price is None:
        return 0
    # An older Gateway can finish an event during an upgrade, after migration 6.
    # Rebuild these verified legacy buckets from totals, never subtract twice.
    connection.execute("UPDATE llm_requests SET uncached_input_tokens=input_total_tokens-cached_input_tokens-cache_write_tokens,pricing_supported=1 WHERE provider=? AND model=? AND occurred_at>=? AND (? IS NULL OR occurred_at<?) AND cost_micro_usd IS NULL AND cost_source='unknown' AND pricing_supported=0 AND provider_usage_schema='hermes-canonical/source-525dbcad' AND cache_write_tokens>0 AND input_total_tokens>=cached_input_tokens+cache_write_tokens AND output_tokens IS NOT NULL", (price['provider'], price['model'], price['starts_at'], price['ends_at'], price['ends_at']))
    cursor = connection.execute("SELECT event_key,uncached_input_tokens,cached_input_tokens,output_tokens,cache_write_tokens FROM llm_requests WHERE provider=? AND model=? AND occurred_at>=? AND (? IS NULL OR occurred_at<?) AND cost_micro_usd IS NULL AND cost_source='unknown' AND pricing_supported=1 AND uncached_input_tokens IS NOT NULL AND cached_input_tokens IS NOT NULL AND output_tokens IS NOT NULL", (price['provider'], price['model'], price['starts_at'], price['ends_at'], price['ends_at']))
    count = 0
    while batch := cursor.fetchmany(500):
        updates = []
        for row in batch:
            costs = estimate_costs(price, row['uncached_input_tokens'], row['cached_input_tokens'], row['output_tokens'], cache_write=row['cache_write_tokens'])
            if any(value is None for value in costs):
                continue
            updates.append((price_id, revision_id, sum(costs), *costs, row['event_key']))
        count += connection.executemany("UPDATE llm_requests SET price_id=?,price_revision_id=?,cost_micro_usd=?,input_cost_micro_usd=?,cached_cost_micro_usd=?,output_cost_micro_usd=?,cache_write_cost_micro_usd=?,cost_source='estimated' WHERE event_key=? AND cost_micro_usd IS NULL AND cost_source='unknown'", updates).rowcount
    return count


def price_rows(connection, page=1, page_size=100, order='asc'):
    result = rows(connection, f"SELECT id,provider,model,input,cached,output,cache_write,valid_from,valid_to,enabled FROM model_prices ORDER BY id {'DESC' if order == 'desc' else 'ASC'} LIMIT ? OFFSET ?", (page_size, (page - 1) * page_size))
    for item in result:
        for field in ("input", "cached", "output", "cache_write"):
            item[field] = float(item[field]) if item[field] is not None else None
        item["enabled"] = bool(item["enabled"])
    return result


def unpriced(connection):
    zone = json.loads(connection.execute("SELECT value_json FROM plugin_settings WHERE key='timezone'").fetchone()[0])
    match = "p.provider=r.provider AND p.model=r.model AND p.enabled=1 AND p.starts_at<=r.occurred_at AND (p.ends_at IS NULL OR p.ends_at>r.occurred_at)"
    missing = rows(connection, f"""SELECT r.provider,r.model,local_day(r.occurred_at,?) AS day,count(*) AS count,
        (SELECT p.id FROM model_prices p WHERE {match} AND p.cache_write IS NULL LIMIT 1) AS existing_price_id,
        CASE WHEN NOT EXISTS(SELECT 1 FROM model_prices p WHERE p.provider=r.provider AND p.model=r.model) THEN '未设置价格'
        WHEN NOT EXISTS(SELECT 1 FROM model_prices p WHERE p.provider=r.provider AND p.model=r.model AND p.enabled=1) THEN '价格已停用'
        WHEN EXISTS(SELECT 1 FROM model_prices p WHERE {match}) THEN '缓存写入未定价' ELSE '日期未覆盖' END AS reason
        FROM llm_requests r WHERE NOT EXISTS(SELECT 1 FROM model_prices p WHERE {match} AND (coalesce(r.cache_write_tokens,0)=0 OR p.cache_write IS NOT NULL))
        GROUP BY r.provider,r.model,day ORDER BY r.provider,r.model,day""", (zone,))
    result = []
    for item in missing:
        previous = result[-1] if result else None
        if previous and (previous['provider'], previous['model'], previous['reason'], previous['existing_price_id']) == (item['provider'], item['model'], item['reason'], item['existing_price_id']) and date.fromisoformat(item['day']) == date.fromisoformat(previous['valid_to']) + timedelta(days=1):
            previous['valid_to'] = item['day']
            previous['request_count'] += item['count']
        else:
            result.append({'id': json.dumps([item['provider'], item['model'], item['day']]), 'provider': item['provider'], 'model': item['model'], 'valid_from': item['day'], 'valid_to': item['day'], 'request_count': item['count'], 'reason': item['reason'], 'existing_price_id': item['existing_price_id'], 'existing_price': None})
    for item in result:
        if item['existing_price_id']:
            existing = dict(connection.execute('SELECT id,provider,model,input,cached,cache_write,output,valid_from,valid_to,enabled FROM model_prices WHERE id=?', (item['existing_price_id'],)).fetchone())
            for field in ('input', 'cached', 'cache_write', 'output'):
                existing[field] = float(existing[field]) if existing[field] is not None else None
            existing['enabled'] = bool(existing['enabled'])
            item['existing_price'] = existing
    return result


def require_department(connection, department_id):
    if not connection.execute("SELECT 1 FROM departments WHERE id=? AND status='active'", (department_id,)).fetchone():
        raise HTTPException(422, "部门不存在或已停用")


def assign(connection, principal, user_ids, department_id):
    if department_id:
        require_department(connection, department_id)
    department_id = department_id or None
    unique = set(user_ids)
    existing = {row[0] for row in connection.execute(f"SELECT id FROM users WHERE status='active' AND id IN ({','.join('?' for _ in unique)})", tuple(unique))}
    if existing != unique:
        raise HTTPException(422, "用户不存在或已停用")
    stamp = now()
    for user_id in unique:
        current = connection.execute("SELECT department_id FROM users WHERE id=?", (user_id,)).fetchone()[0]
        if current == department_id:
            continue
        connection.execute("UPDATE department_membership SET valid_to=? WHERE user_id=? AND valid_to IS NULL", (stamp, user_id))
        if department_id is not None:
            connection.execute("INSERT INTO department_membership VALUES(?,?,?,?,NULL)", (uuid4().hex, user_id, department_id, stamp))
        connection.execute("UPDATE users SET department_id=? WHERE id=?", (department_id, user_id))
        audit(connection, principal, "people.move", user_id)
