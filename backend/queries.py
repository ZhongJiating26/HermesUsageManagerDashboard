from datetime import datetime, timedelta
from fastapi import HTTPException

from .security import require


def where(window, principal, alias="", tools=False):
    require(principal, "read")
    prefix = f"{alias}." if alias else ""
    clauses = [f"{prefix}occurred_at>=?", f"{prefix}occurred_at<?"]
    values = [window.start, window.end]
    for field, value in (("department_id", window.department_id), ("user_id", window.user_id), ("department_id", principal.department_id if principal.role == "department" else None), ("user_id", principal.user_id if principal.role == "user" else None)):
        if value:
            clauses.append(f"{prefix}{field}=?")
            values.append(value)
    if tools:
        clauses.append(f"{prefix}tool_type='mcp'")
        if window.server_id:
            clauses.append(f"{prefix}mcp_server_id=?")
            values.append(window.server_id)
    return " AND ".join(clauses), values


def usd(value):
    return value / 1_000_000 if value is not None else None


def rows(connection, sql, values=()):
    result = [dict(item) for item in connection.execute(sql, values).fetchmany(10001)]
    if len(result) > 10000:
        raise HTTPException(422, {'code': 'RESULT_TOO_LARGE', 'message': '分组结果超过 10000 条，请缩小筛选范围'})
    return result


def coverage(connection):
    from .quality import collection
    return {"scope": "configured_database", "profile_total": connection.execute("SELECT count(*) FROM profiles WHERE enabled=1").fetchone()[0], "profile_reporting": connection.execute("SELECT count(*) FROM (SELECT instance_id,profile_id FROM llm_requests UNION SELECT instance_id,profile_id FROM tool_calls)").fetchone()[0], "collection": collection(connection)['status']}


def analytics(connection, window, principal):
    condition, values = where(window, principal)
    tool_condition, tool_values = where(window, principal, tools=True)
    sums = "sum(uncached_input_tokens) AS input,sum(cached_input_tokens) AS cached,sum(output_tokens) AS output,sum(total_tokens) AS total_tokens,sum(cost_micro_usd) AS cost,sum(input_cost_micro_usd) AS input_cost,sum(cached_cost_micro_usd) AS cached_cost,sum(output_cost_micro_usd) AS output_cost"
    kpis = dict(connection.execute(f"SELECT count(*) AS count,count(DISTINCT user_id) AS active,sum(cost_micro_usd IS NULL) AS unknown_cost,sum(cached_input_tokens IS NULL) AS unknown_cache,{sums} FROM llm_requests WHERE {condition}", values).fetchone())
    count = kpis.pop("count")
    if count == 0:
        kpis = {key: 0 if value is None else value for key, value in kpis.items()}
    for field in ("cost", "input_cost", "cached_cost", "output_cost"):
        kpis[field] = usd(kpis[field])
    distributions = {}
    columns = {"department": ("department_id", "departments"), "user": ("user_id", "users"), "model": ("model", None), "provider": ("provider", None)}
    for dimension, (column, table) in columns.items():
        grouped = rows(connection, f"SELECT {column} AS id,{sums} FROM llm_requests WHERE {condition} GROUP BY {column} ORDER BY sum(total_tokens) DESC", values)
        names = {item["id"]: item["name"] for item in connection.execute(f"SELECT id,name FROM {table}")} if table else {}
        for item in grouped:
            item["id"] = item["id"] or ""
            item["name"] = names.get(item["id"], item["id"] or "未归属")
            item["tokens"] = item.pop("total_tokens")
            item["cost"] = usd(item["cost"])
            for field in ("input_cost", "cached_cost", "output_cost"):
                item.pop(field)
        distributions[dimension] = grouped
    kpis["primary_model"] = distributions["model"][0]["name"] if distributions["model"] and distributions["model"][0]['tokens'] is not None else None
    kpis.update(dict(connection.execute(f"SELECT count(*) FILTER(WHERE status='success') AS successful_requests,count(*) FILTER(WHERE status='failed') AS failed_requests,count(*) FILTER(WHERE request_kind='auxiliary') AS auxiliary_requests,count(DISTINCT session_key) FILTER(WHERE user_id IS NULL) AS unresolved_sessions FROM llm_requests WHERE {condition}", values).fetchone()))
    activity_condition, activity_tools = where(window, principal)
    activity = f"SELECT occurred_at,user_id FROM llm_requests WHERE {condition} UNION ALL SELECT occurred_at,user_id FROM tool_calls WHERE {activity_condition}"
    activity_values = [*values, *activity_tools]
    kpis['active'] = connection.execute(f"SELECT count(DISTINCT user_id) FROM ({activity})", activity_values).fetchone()[0]
    active_days = {item['day']: item['active'] for item in rows(connection, f"SELECT local_day(occurred_at,?) AS day,count(DISTINCT user_id) AS active FROM ({activity}) GROUP BY day", [window.tz, *activity_values])}
    daily = {item["day"]: item for item in rows(connection, f"SELECT local_day(occurred_at,?) AS day,count(DISTINCT user_id) AS active,{sums} FROM llm_requests WHERE {condition} GROUP BY day", [window.tz, *values])}
    calls = {item["day"]: item["calls"] for item in rows(connection, f"SELECT local_day(occurred_at,?) AS day,count(*) AS calls FROM tool_calls WHERE {tool_condition} GROUP BY day", [window.tz, *tool_values])}
    trend = []
    day = datetime.fromisoformat(window.start).astimezone(window.zone).date()
    end = datetime.fromisoformat(window.end).astimezone(window.zone).date()
    while day < end or (day == end and datetime.fromisoformat(window.end).astimezone(window.zone).time().isoformat() != '00:00:00'):
        key = day.isoformat()
        item = daily.get(key, {"day": key, "input": 0, "cached": 0, "output": 0, "total_tokens": 0, "active": 0})
        item['active'] = active_days.get(key, 0)
        trend.append({field: item[field] for field in ("day", "input", "cached", "output", "total_tokens", "active")} | {"calls": calls.get(key, 0)})
        day += timedelta(days=1)
    tools = rows(connection, f"SELECT mcp_server_id AS server_id,tool_id, min(tool_name) AS name,count(*) AS calls,sum(status='failed') AS failed,cast(avg(duration_ms) AS INTEGER) AS duration_ms FROM tool_calls WHERE {tool_condition} GROUP BY mcp_server_id,tool_id ORDER BY calls DESC,server_id,tool_id", tool_values)
    for item in tools:
        item["id"] = f"{item['server_id']}:{item['tool_id']}"
    return {"count": count, "kpis": kpis, "trend": trend, "distributions": distributions, "tools": tools}


def request_rows(connection, window, principal, page=1, page_size=20, sort="time", order="desc", search="", event_id=None):
    condition, values = where(window, principal, "r")
    if search:
        condition += " AND (r.event_key LIKE ? OR r.model LIKE ? OR r.provider LIKE ?)"
        values += [f"%{search}%"] * 3
    if event_id:
        condition += " AND r.event_key=?"
        values.append(event_id)
    total = connection.execute(f"SELECT count(*) FROM llm_requests r WHERE {condition}", values).fetchone()[0]
    column = {"time": "occurred_at", "input": "uncached_input_tokens", "output": "output_tokens"}[sort]
    result = rows(connection, f"SELECT r.*,s.source_session_id FROM llm_requests r JOIN sessions s USING(session_key) WHERE {condition} ORDER BY r.{column} {'DESC' if order == 'desc' else 'ASC'},r.event_key LIMIT ? OFFSET ?", [*values, page_size, (page - 1) * page_size])
    return [{"id": item["event_key"], "time": item["occurred_at"], "department_id": item["department_id"] or "", "user_id": item["user_id"] or "", "profile": item["profile_id"], "instance_id": item["instance_id"], "session_id": item["source_session_id"], "session_key": item["session_key"], "model": item["model"], "provider": item["provider"], "status": item["status"], "input": item["uncached_input_tokens"], "input_total_tokens": item["input_total_tokens"], "total_tokens": item["total_tokens"], "cached": item["cached_input_tokens"], "output": item["output_tokens"], "duration_ms": item["duration_ms"], "cost": usd(item["cost_micro_usd"]), "cost_source": item["cost_source"], "price_id": item["price_id"]} for item in result], total


def session_rows(connection, window, principal, page=1, page_size=20, sort="time", order="desc", search="", session_id=None):
    require(principal, "audit")
    condition, values = where(window, principal, "r")
    if session_id:
        condition += " AND r.session_key=?"
        values.append(session_id)
    if search:
        condition += " AND s.source_session_id LIKE ?"
        values.append(f"%{search}%")
    grouped = f"SELECT r.session_key AS id,min(r.occurred_at) AS time,CASE WHEN count(DISTINCT coalesce(r.department_id,''))=1 THEN min(r.department_id) END AS department_id,CASE WHEN count(DISTINCT coalesce(r.user_id,''))=1 THEN min(r.user_id) END AS user_id,min(r.profile_id) AS profile,'unknown' AS platform,sum(r.uncached_input_tokens) AS input,sum(r.cached_input_tokens) AS cached,sum(r.output_tokens) AS output FROM llm_requests r JOIN sessions s USING(session_key) WHERE {condition} GROUP BY r.session_key"
    total = connection.execute(f"SELECT count(*) FROM ({grouped})", values).fetchone()[0]
    column = {"time": "time", "input": "input", "output": "output"}[sort]
    result = rows(connection, f"SELECT * FROM ({grouped}) ORDER BY {column} {'DESC' if order == 'desc' else 'ASC'},id LIMIT ? OFFSET ?", [*values, page_size, (page - 1) * page_size])
    tool_condition, tool_values = where(window, principal, "t", tools=True)
    for item in result:
        item["department_id"], item["user_id"] = item["department_id"] or "", item["user_id"] or ""
        item["mcp_calls"] = connection.execute(f"SELECT count(*) FROM tool_calls t WHERE {tool_condition} AND session_key=?", [*tool_values, item["id"]]).fetchone()[0]
    return result, total
