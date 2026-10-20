import csv
import io
import json
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from uuid import uuid4
from threading import RLock

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute

from . import admin, queries, quality
from .adapters.session_content import HermesSessionContentProvider
from .adapters.hermes import storage_path
from .db import Store, now
from .schemas import DepartmentBody, Envelope, MoveBody, PriceBody, SettingsBody, UserBody, get_window
from .security import get_principal, require
from .responses import Health, AnalyticsEnvelope, KPIEnvelope, TrendEnvelope, DistributionEnvelope, ToolsEnvelope


class SafeRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def wrapped(request):
            try:
                return await handler(request)
            except HTTPException as error:
                detail = error.detail if isinstance(error.detail, dict) else {"code": "REQUEST_REJECTED", "message": str(error.detail)}
                return JSONResponse({"error": {**detail, "request_id": uuid4().hex}}, status_code=error.status_code)
            except RequestValidationError:
                return JSONResponse({"error": {"code": "VALIDATION_ERROR", "message": "请求参数格式不正确", "request_id": uuid4().hex}}, status_code=422)
            except ResponseValidationError:
                return JSONResponse({'error': {'code': 'RESPONSE_INVALID', 'message': '接口输出不符合契约', 'request_id': uuid4().hex}}, status_code=502)
            except sqlite3.IntegrityError:
                return JSONResponse({"error": {"code": "CONFLICT", "message": "记录冲突或数据约束未满足", "request_id": uuid4().hex}}, status_code=409)
            except (sqlite3.Error, RuntimeError, ValueError, OSError):
                return JSONResponse({"error": {"code": "STORAGE_UNAVAILABLE", "message": "存储不可用，请检查配置或稍后重试", "request_id": uuid4().hex}}, status_code=503)
        return wrapped


router = APIRouter(route_class=SafeRoute)
runtime_lock = RLock()


@dataclass
class Runtime:
    store: Store
    anchor: str | None = None
    content_provider: object = None


@lru_cache(maxsize=16)
def configured_runtime(path):
    return Runtime(Store(path), content_provider=HermesSessionContentProvider())


def get_runtime():
    with runtime_lock:
        return configured_runtime(str(storage_path()))


def data_source():
    return "live"


def envelope(runtime, data, window=None, **extra):
    with runtime.store.read() as connection:
        meta = {"data_source": runtime.store.source, "tz": window.tz if window else "Asia/Shanghai", "coverage": queries.coverage(connection), **extra}
    if window:
        meta.update({"from": window.start, "to": window.end})
    return {"data": data, "meta": meta}


@router.get("/health", response_model=Health)
def health(request: Request, source: str = Depends(data_source)):
    storage = "unavailable"
    collection = 'unavailable'
    try:
        runtime = getattr(request.app.state, "hum_runtime", None) or get_runtime()
        with runtime.store.read() as connection:
            connection.execute("SELECT count(*) FROM schema_migrations").fetchone()
            collection = quality.collection(connection)['status']
        storage = "ready"
    except (RuntimeError, ValueError, sqlite3.Error, OSError):
        pass
    return {"status": "ok", "plugin": "hermes-usage-manager", "version": "0.6.0", "milestone": "M4", "data_source": source, "capabilities": {"storage": storage, "collection": collection, "hermes_runtime": "unverified", "business_api": True}}


@router.get('/quality', response_model=Envelope)
def data_quality(window=Depends(get_window), runtime=Depends(get_runtime), principal=Depends(get_principal)):
    with runtime.store.read() as connection:
        result = quality.details(connection, window, principal)
    return envelope(runtime, result, window)


@router.get("/filters", response_model=Envelope)
def filters(runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "read")
    with runtime.store.read() as connection:
        departments = queries.rows(connection, "SELECT id,name FROM departments WHERE status='active'" + (" AND id=?" if principal.role == "department" else ""), (principal.department_id,) if principal.role == "department" else ())
        users = queries.rows(connection, "SELECT id,name,external_id,coalesce(department_id,'') AS department_id,profile FROM users WHERE status='active'" + (" AND department_id=?" if principal.role == "department" else " AND id=?" if principal.role == "user" else ""), (principal.department_id,) if principal.role == "department" else (principal.user_id,) if principal.role == "user" else ())
        servers = queries.rows(connection, "SELECT DISTINCT server_id AS id,server_id AS name FROM mcp_tools WHERE enabled=1" + (" AND server_id IN (SELECT mcp_server_id FROM tool_calls WHERE department_id=?)" if principal.role == 'department' else " AND server_id IN (SELECT mcp_server_id FROM tool_calls WHERE user_id=?)" if principal.role == 'user' else ''), (principal.department_id,) if principal.role == 'department' else (principal.user_id,) if principal.role == 'user' else ())
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return envelope(runtime, {"departments": departments, "users": users, "servers": servers, "anchor": runtime.anchor or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(), "role": principal.role})


@router.get("/overview/summary", response_model=AnalyticsEnvelope)
@router.get("/overview/kpis", response_model=KPIEnvelope)
@router.get("/overview/trend", response_model=TrendEnvelope)
@router.get("/usage/trend", response_model=TrendEnvelope)
@router.get("/usage/departments", response_model=DistributionEnvelope)
@router.get("/usage/distribution", response_model=DistributionEnvelope)
@router.get("/usage/ranking/users", response_model=DistributionEnvelope)
@router.get("/mcp/trend", response_model=TrendEnvelope)
@router.get("/mcp/tools/ranking", response_model=ToolsEnvelope)
def analytics(request: Request, dimension: Literal["department", "user", "provider", "model"] = "department", metric: Literal["tokens", "cost"] = "tokens", window=Depends(get_window), runtime=Depends(get_runtime), principal=Depends(get_principal)):
    with runtime.store.read() as connection:
        data = queries.analytics(connection, window, principal)
    path = request.url.path
    if path.endswith("/kpis"):
        data = data["kpis"]
    elif path.endswith("/trend"):
        data = data["trend"]
    elif path.endswith("/departments"):
        data = data["distributions"]["department"]
    elif path.endswith("/distribution"):
        data = data["distributions"][dimension]
    elif path.endswith("/users"):
        data = sorted(data["distributions"]["user"], key=lambda item: item[metric] or 0, reverse=True)[:10]
    elif path.endswith("/ranking"):
        data = data["tools"]
    return envelope(runtime, data, window)


@router.get("/mcp/services", response_model=Envelope)
def services(page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100), runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "read")
    with runtime.store.read() as connection:
        condition = "enabled=1"
        values = []
        if principal.role in ('department', 'user'):
            column, scope = ('department_id', principal.department_id) if principal.role == 'department' else ('user_id', principal.user_id)
            condition += f" AND EXISTS(SELECT 1 FROM tool_calls t WHERE t.mcp_server_id=mcp_tools.server_id AND t.tool_id=mcp_tools.tool_id AND t.{column}=?)"
            values.append(scope)
        total = connection.execute(f"SELECT count(*) FROM mcp_tools WHERE {condition}", values).fetchone()[0]
        data = queries.rows(connection, f"SELECT server_id AS id,server_id AS name,tool_id,display_name FROM mcp_tools WHERE {condition} ORDER BY server_id,tool_id LIMIT ? OFFSET ?", [*values, page_size, (page - 1) * page_size])
    return envelope(runtime, data, total=total, page=page, page_size=page_size)


@router.get("/requests", response_model=Envelope)
@router.get("/sessions", response_model=Envelope)
def records(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), sort: Literal["time", "input", "output"] = "time", order: Literal["asc", "desc"] = "desc", search: str = Query("", max_length=200), window=Depends(get_window), runtime=Depends(get_runtime), principal=Depends(get_principal)):
    with runtime.store.read() as connection:
        method = queries.session_rows if request.url.path.endswith("/sessions") else queries.request_rows
        data, total = method(connection, window, principal, page, page_size, sort, order, search)
    return envelope(runtime, data, window, total=total, page=page, page_size=page_size)


@router.get("/requests/{event_id}", response_model=Envelope)
def request_detail(event_id: str, window=Depends(get_window), runtime=Depends(get_runtime), principal=Depends(get_principal)):
    with runtime.store.read() as connection:
        data, _ = queries.request_rows(connection, window, principal, event_id=event_id)
    if not data:
        raise HTTPException(404, "请求不存在或不在可见范围")
    return envelope(runtime, data[0], window)


@router.get("/sessions/{session_id}", response_model=Envelope)
@router.get("/sessions/{session_id}/timeline", response_model=Envelope)
def session_detail(request: Request, session_id: str, offset: int = Query(0, ge=0, le=100000), limit: int = Query(100, ge=1, le=200), window=Depends(get_window), runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "audit")
    with runtime.store.read() as connection:
        condition, values = queries.where(window, principal, "r")
        exists = connection.execute(f"SELECT 1 FROM llm_requests r WHERE r.session_key=? AND {condition}", [session_id, *values]).fetchone()
        if not exists:
            raise HTTPException(404, "会话不存在或不在可见范围")
        session = dict(connection.execute("SELECT session_key AS id,profile_id AS profile,platform,started_at AS time FROM sessions WHERE session_key=?", (session_id,)).fetchone())
        owner = dict(connection.execute('SELECT instance_id,profile_id,source_session_id FROM sessions WHERE session_key=?', (session_id,)).fetchone())
    timeline = request.url.path.endswith("/timeline")
    if timeline:
        try:
            require(principal, 'audit_detail')
            if runtime.content_provider is None:
                raise HTTPException(503, {'code': 'SESSION_CONTENT_UNAVAILABLE', 'message': '会话正文源未接入'})
            if runtime.store.source == 'mock' and callable(runtime.content_provider):
                messages = runtime.content_provider(session_id)
                content = {'messages': messages[offset:offset + limit], 'pagination': {'offset': offset, 'limit': limit, 'has_more': len(messages) > offset + limit, 'returned': len(messages[offset:offset + limit])}}
            else:
                content = runtime.content_provider.read(owner['instance_id'], owner['profile_id'], owner['source_session_id'], offset, limit)
        except HTTPException as error:
            with runtime.store.transaction() as connection:
                admin.audit(connection, principal, 'sessions.timeline', session_id, 'denied' if error.status_code == 403 else 'unavailable')
            raise
        except Exception:
            with runtime.store.transaction() as connection:
                admin.audit(connection, principal, 'sessions.timeline', session_id, 'unavailable')
            raise HTTPException(503, {'code': 'SESSION_CONTENT_UNAVAILABLE', 'message': '会话正文读取失败'}) from None
        with runtime.store.transaction() as connection:
            admin.audit(connection, principal, 'sessions.timeline', session_id)
        session.update({'source_id': owner['source_session_id'], 'title': content.get('title')})
        return envelope(runtime, {'session': session, **content})
    with runtime.store.transaction() as connection:
        admin.audit(connection, principal, 'sessions.detail', session_id)
    return envelope(runtime, session)


@router.get("/people/users", response_model=Envelope)
@router.get("/people/departments", response_model=Envelope)
@router.get("/models/prices", response_model=Envelope)
@router.get("/models/unpriced", response_model=Envelope)
@router.get("/audit/access-logs", response_model=Envelope)
def management(request: Request, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100), sort: Literal['id', 'name', 'time'] = 'id', order: Literal['asc', 'desc'] = 'asc', runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "manage")
    with runtime.store.read() as connection:
        last = request.url.path.split('/')[-1]
        if last == "prices":
            total = connection.execute('SELECT count(*) FROM model_prices').fetchone()[0]
            data = admin.price_rows(connection, page, page_size, order)
        elif last == "unpriced":
            data = admin.unpriced(connection)
            data.sort(key=lambda item: item['id'], reverse=order == 'desc')
            total = len(data)
            data = data[(page - 1) * page_size:page * page_size]
        else:
            table = {'users': 'users', 'departments': 'departments', 'access-logs': 'audit_access_logs'}[last]
            fields = {'users': "id,name,external_id,coalesce(department_id,'') AS department_id,profile,platform", 'departments': 'id,name', 'access-logs': '*'}[last]
            condition = "WHERE status='active'" if last != 'access-logs' else ''
            key = 'occurred_at' if last == 'access-logs' and sort == 'time' else 'name' if sort == 'name' and last in ('users', 'departments') else 'id'
            direction = 'DESC' if order == 'desc' else 'ASC'
            total = connection.execute(f'SELECT count(*) FROM {table} {condition}').fetchone()[0]
            data = queries.rows(connection, f'SELECT {fields} FROM {table} {condition} ORDER BY {key} {direction},id LIMIT ? OFFSET ?', (page_size, (page - 1) * page_size))
    return envelope(runtime, data, total=total, page=page, page_size=page_size)


@router.post("/models/prices", response_model=Envelope)
@router.patch("/models/prices/{price_id}", response_model=Envelope)
def save_price(body: PriceBody, price_id: str = "", runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "write")
    with runtime.store.transaction() as connection:
        price_id = admin.save_price(connection, principal, body, price_id)
    return envelope(runtime, {"id": price_id})


@router.post("/people/departments", response_model=Envelope)
@router.patch("/people/departments/{department_id}", response_model=Envelope)
def save_department(body: DepartmentBody, department_id: str = "", runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "write")
    with runtime.store.transaction() as connection:
        if department_id:
            admin.require_department(connection, department_id)
            connection.execute("UPDATE departments SET name=? WHERE id=?", (body.name, department_id))
        else:
            department_id = f"d-{uuid4().hex}"
            connection.execute("INSERT INTO departments(id,name) VALUES(?,?)", (department_id, body.name))
        admin.audit(connection, principal, "department.save", department_id)
    return envelope(runtime, {"id": department_id, "name": body.name})


@router.delete("/people/departments/{department_id}", response_model=Envelope)
def delete_department(department_id: str, runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "write")
    with runtime.store.transaction() as connection:
        admin.require_department(connection, department_id)
        if connection.execute("SELECT 1 FROM users WHERE department_id=? AND status='active'", (department_id,)).fetchone():
            raise HTTPException(409, "部门内仍有成员，请先迁移成员")
        connection.execute("UPDATE departments SET status='inactive' WHERE id=?", (department_id,))
        admin.audit(connection, principal, "department.delete", department_id)
    return envelope(runtime, {"ok": True})


@router.post("/people/assignments/move", response_model=Envelope)
def move(body: MoveBody, runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "write")
    with runtime.store.transaction() as connection:
        admin.assign(connection, principal, body.user_ids, body.department_id)
    return envelope(runtime, {"ok": True})


@router.post("/people/users", response_model=Envelope)
@router.patch("/people/users/{user_id}", response_model=Envelope)
def save_user(body: UserBody, user_id: str = "", runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "write")
    with runtime.store.transaction() as connection:
        admin.require_department(connection, body.department_id)
        if user_id:
            if not connection.execute("SELECT 1 FROM users WHERE id=? AND status='active'", (user_id,)).fetchone():
                raise HTTPException(404, "用户不存在")
            connection.execute("UPDATE users SET name=?,external_id=?,profile=?,platform=? WHERE id=?", (body.name, body.external_id, body.profile, body.platform, user_id))
        else:
            user_id = f"u-{uuid4().hex}"
            connection.execute("INSERT INTO users(id,name,external_id,profile,platform) VALUES(?,?,?,?,?)", (user_id, body.name, body.external_id, body.profile, body.platform))
        admin.assign(connection, principal, [user_id], body.department_id)
        admin.audit(connection, principal, "people.save", user_id)
    return envelope(runtime, {"id": user_id})


@router.get("/settings", response_model=Envelope)
@router.patch("/settings", response_model=Envelope)
def settings(request: Request, body: SettingsBody | None = None, runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "manage")
    with runtime.store.transaction() as connection:
        if request.method == "PATCH":
            if body is None:
                raise HTTPException(422, "缺少设置")
            connection.execute("INSERT INTO plugin_settings VALUES('export_enabled',?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json", (json.dumps(body.export_enabled),))
            admin.audit(connection, principal, "settings.save", "export_enabled")
        data = {item["key"]: json.loads(item["value_json"]) for item in connection.execute("SELECT * FROM plugin_settings")}
    return envelope(runtime, data)


@router.get("/exports/requests.csv")
def export(window=Depends(get_window), runtime=Depends(get_runtime), principal=Depends(get_principal)):
    require(principal, "read")
    with runtime.store.transaction() as connection:
        setting = connection.execute("SELECT value_json FROM plugin_settings WHERE key='export_enabled'").fetchone()
        if not setting or json.loads(setting[0]) is not True:
            raise HTTPException(403, "CSV 导出未启用")
        data, total = queries.request_rows(connection, window, principal, page_size=10001)
        if total > 10000:
            raise HTTPException(422, "导出上限为 10000 条，请缩小日期范围")
        admin.audit(connection, principal, "export.requests", str(total))
    stream = io.StringIO()
    fields = ["id", "time", "provider", "model", "input", "cached", "output", "cost", "cost_source"]
    writer = csv.writer(stream)
    writer.writerow(fields)
    for item in data:
        values = []
        for field in fields:
            value = "" if item[field] is None else str(item[field])
            if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return Response('\ufeff' + stream.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="usage-requests.csv"'})
