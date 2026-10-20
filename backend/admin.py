import json
from datetime import date, timedelta
from uuid import uuid4

from fastapi import HTTPException

from .db import now
from .queries import rows
from .schemas import price_period


def audit(connection, principal, action, target, result="ok"):
    connection.execute("INSERT INTO audit_access_logs VALUES(?,?,?,?,?,?,?,?)", (uuid4().hex, principal.id, action, action.split('.')[0], target, now(), result, uuid4().hex))


def save_price(connection, principal, body, price_id=""):
    zone = json.loads(connection.execute("SELECT value_json FROM plugin_settings WHERE key='timezone'").fetchone()[0])
    start, end = price_period(body, zone)
    if price_id and not connection.execute("SELECT 1 FROM model_prices WHERE id=?", (price_id,)).fetchone():
        raise HTTPException(404, "价格配置不存在")
    overlap = connection.execute("SELECT id FROM model_prices WHERE provider=? AND model=? AND enabled=1 AND id<>? AND starts_at<coalesce(?,'9999') AND coalesce(ends_at,'9999')>? LIMIT 1", (body.provider, body.model, price_id, end, start)).fetchone()
    if body.enabled and overlap:
        raise HTTPException(409, "同一提供商和模型的启用价格区间不能重叠")
    price_id = price_id or f"price-{uuid4().hex}"
    values = (price_id, body.provider, body.model, str(body.input), str(body.cached), str(body.output), str(body.valid_from), str(body.valid_to) if body.valid_to else None, start, end, int(body.enabled))
    connection.execute("INSERT INTO model_prices(id,provider,model,input,cached,output,valid_from,valid_to,starts_at,ends_at,enabled) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,model=excluded.model,input=excluded.input,cached=excluded.cached,output=excluded.output,valid_from=excluded.valid_from,valid_to=excluded.valid_to,starts_at=excluded.starts_at,ends_at=excluded.ends_at,enabled=excluded.enabled", values)
    config = body.model_dump(mode="json")
    connection.execute("INSERT INTO price_revisions VALUES(?,?,?,?,?)", (uuid4().hex, price_id, principal.id, now(), json.dumps(config)))
    audit(connection, principal, "price.save", price_id)
    return price_id


def price_rows(connection, page=1, page_size=100, order='asc'):
    result = rows(connection, f"SELECT id,provider,model,input,cached,output,valid_from,valid_to,enabled FROM model_prices ORDER BY id {'DESC' if order == 'desc' else 'ASC'} LIMIT ? OFFSET ?", (page_size, (page - 1) * page_size))
    for item in result:
        for field in ("input", "cached", "output"):
            item[field] = float(item[field])
        item["enabled"] = bool(item["enabled"])
    return result


def unpriced(connection):
    zone = json.loads(connection.execute("SELECT value_json FROM plugin_settings WHERE key='timezone'").fetchone()[0])
    missing = rows(connection, "SELECT r.provider,r.model,local_day(r.occurred_at,?) AS day,count(*) AS count,CASE WHEN NOT EXISTS(SELECT 1 FROM model_prices p WHERE p.provider=r.provider AND p.model=r.model) THEN '未设置价格' WHEN NOT EXISTS(SELECT 1 FROM model_prices p WHERE p.provider=r.provider AND p.model=r.model AND p.enabled=1) THEN '价格已停用' ELSE '日期未覆盖' END AS reason FROM llm_requests r WHERE NOT EXISTS(SELECT 1 FROM model_prices p WHERE p.provider=r.provider AND p.model=r.model AND p.enabled=1 AND p.starts_at<=r.occurred_at AND (p.ends_at IS NULL OR p.ends_at>r.occurred_at)) GROUP BY r.provider,r.model,day ORDER BY r.provider,r.model,day", (zone,))
    result = []
    for item in missing:
        if result and (result[-1]["provider"], result[-1]["model"]) == (item["provider"], item["model"]) and date.fromisoformat(item["day"]) == date.fromisoformat(result[-1]["valid_to"]) + timedelta(days=1):
            result[-1]["valid_to"] = item["day"]
            result[-1]["request_count"] += item["count"]
        else:
            result.append({"id": json.dumps([item["provider"], item["model"], item["day"]]), "provider": item["provider"], "model": item["model"], "valid_from": item["day"], "valid_to": item["day"], "request_count": item["count"], "reason": item["reason"]})
    return result


def require_department(connection, department_id):
    if not connection.execute("SELECT 1 FROM departments WHERE id=? AND status='active'", (department_id,)).fetchone():
        raise HTTPException(422, "部门不存在或已停用")


def assign(connection, principal, user_ids, department_id):
    require_department(connection, department_id)
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
        connection.execute("INSERT INTO department_membership VALUES(?,?,?,?,NULL)", (uuid4().hex, user_id, department_id, stamp))
        connection.execute("UPDATE users SET department_id=? WHERE id=?", (department_id, user_id))
        audit(connection, principal, "people.move", user_id)
