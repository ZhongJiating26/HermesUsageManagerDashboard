import hashlib
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, Field, model_validator

from .db import utc, now
from .identity import resolve


def key(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class ModelEvent(BaseModel):
    instance_id: str
    profile_id: str
    source_event_id: str
    session_id: str
    api_request_id: str
    attempt_no: int = Field(default=0, ge=0)
    request_kind: str = "main"
    provider: str
    model: str
    user_id: str | None = None
    department_id: str | None = None
    external_user_id: str | None = None
    platform: str | None = None
    provider_usage_schema: str = 'normalized/v1'
    error_code: str | None = None
    turn_id: str | None = None
    time_source: str = 'normalized'
    cache_write_tokens: int | None = Field(default=None, ge=0)
    pricing_supported: bool = True
    occurred_at: datetime
    status: str = "success"
    input_total_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_usage(self):
        if self.occurred_at.tzinfo is None or self.status not in ("success", "failed") or self.request_kind not in ("main", "auxiliary"):
            raise ValueError("Invalid normalized event")
        if self.input_total_tokens is not None and self.cached_input_tokens is not None and self.cached_input_tokens > self.input_total_tokens:
            raise ValueError("Cached input cannot exceed total input")
        return self


class ToolEvent(BaseModel):
    instance_id: str
    profile_id: str
    source_event_id: str
    session_id: str
    user_id: str | None = None
    department_id: str | None = None
    external_user_id: str | None = None
    platform: str | None = None
    turn_id: str | None = None
    time_source: str = 'normalized'
    tool_id: str
    tool_name: str
    tool_type: str = "unknown"
    mcp_server_id: str | None = None
    status: str = "success"
    occurred_at: datetime
    duration_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_tool(self):
        if self.occurred_at.tzinfo is None or self.tool_type not in ("mcp", "local", "unknown") or self.status not in ("success", "failed"):
            raise ValueError("Invalid tool event")
        if self.tool_type == "mcp" and not self.mcp_server_id:
            self.tool_type = "unknown"
        return self


def session(connection, event):
    session_key = key(event.instance_id, event.profile_id, event.session_id)
    timestamp = utc(event.occurred_at)
    connection.execute("INSERT OR IGNORE INTO instances VALUES(?,?)", (event.instance_id, event.instance_id))
    connection.execute("INSERT OR IGNORE INTO profiles(instance_id,id,display_name) VALUES(?,?,?)", (event.instance_id, event.profile_id, event.profile_id))
    connection.execute("INSERT INTO sessions(session_key,instance_id,profile_id,source_session_id,user_id,department_id,started_at,last_at,platform) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(session_key) DO UPDATE SET started_at=min(started_at,excluded.started_at),last_at=max(last_at,excluded.last_at),platform=CASE WHEN platform='unknown' THEN excluded.platform ELSE platform END", (session_key, event.instance_id, event.profile_id, event.session_id, event.user_id, event.department_id, timestamp, timestamp, event.platform or 'unknown'))
    return session_key


def ingest_model(connection, event):
    event_key = key(event.instance_id, event.profile_id, "model", event.source_event_id)
    if connection.execute("SELECT 1 FROM llm_requests WHERE event_key=?", (event_key,)).fetchone():
        return False
    user_id, department_id, identity_status = resolve(connection, event)
    event = event.model_copy(update={'user_id': user_id, 'department_id': department_id})
    session_key = session(connection, event)
    timestamp = utc(event.occurred_at)
    input_total, cached, output = event.input_total_tokens, event.cached_input_tokens, event.output_tokens
    uncached = input_total - cached if input_total is not None and cached is not None else None
    total = input_total + output if input_total is not None and output is not None else None
    price = connection.execute("SELECT * FROM model_prices WHERE provider=? AND model=? AND enabled=1 AND starts_at<=? AND (ends_at IS NULL OR ends_at>?)", (event.provider, event.model, timestamp, timestamp)).fetchone()
    costs = [None, None, None]
    if price and event.pricing_supported and uncached is not None and cached is not None and output is not None:
        costs = [int((Decimal(price[field]) * tokens).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) for field, tokens in zip(("input", "cached", "output"), (uncached, cached, output))]
    cost = sum(costs) if all(value is not None for value in costs) else None
    fields = {"event_key": event_key, "instance_id": event.instance_id, "profile_id": event.profile_id, "source_event_id": event.source_event_id, "session_key": session_key, "api_request_id": event.api_request_id, "attempt_no": event.attempt_no, "request_kind": event.request_kind, "provider": event.provider, "model": event.model, "user_id": event.user_id, "department_id": event.department_id, "occurred_at": timestamp, "status": event.status, "input_total_tokens": input_total, "cached_input_tokens": cached, "uncached_input_tokens": uncached, "output_tokens": output, "total_tokens": total, "duration_ms": event.duration_ms, "price_id": price["id"] if price else None, "cost_micro_usd": cost, "cost_source": "estimated" if cost is not None else "unknown", "input_cost_micro_usd": costs[0], "cached_cost_micro_usd": costs[1], "output_cost_micro_usd": costs[2]}
    revision = connection.execute("SELECT id FROM price_revisions WHERE price_id=? ORDER BY changed_at DESC,id DESC LIMIT 1", (price["id"],)).fetchone() if price else None
    fields["price_revision_id"] = revision[0] if revision else None
    fields.update(provider_usage_schema=event.provider_usage_schema, identity_status=identity_status, error_code=event.error_code)
    fields.update(turn_id=event.turn_id, time_source=event.time_source, cache_write_tokens=event.cache_write_tokens, pricing_supported=int(event.pricing_supported))
    if event.turn_id:
        connection.execute('INSERT OR IGNORE INTO turns VALUES(?,?,?,?)', (key(session_key, event.turn_id), session_key, event.turn_id, timestamp))
    connection.execute(f"INSERT INTO llm_requests({','.join(fields)}) VALUES({','.join('?' for _ in fields)})", tuple(fields.values()))
    connection.execute("INSERT INTO event_inbox(event_key,type,received_at,status) VALUES(?,?,?,?) ON CONFLICT(event_key) DO UPDATE SET status='done',error_code=NULL", (event_key, "model", now(), "done"))
    return True


def ingest_tool(connection, event):
    event_key = key(event.instance_id, event.profile_id, "tool", event.source_event_id)
    if connection.execute("SELECT 1 FROM tool_calls WHERE event_key=?", (event_key,)).fetchone():
        return False
    user_id, department_id, identity_status = resolve(connection, event)
    event = event.model_copy(update={'user_id': user_id, 'department_id': department_id})
    session_key = session(connection, event)
    fields = {"event_key": event_key, "instance_id": event.instance_id, "profile_id": event.profile_id, "source_event_id": event.source_event_id, "session_key": session_key, "user_id": event.user_id, "department_id": event.department_id, "tool_id": event.tool_id, "tool_name": event.tool_name, "tool_type": event.tool_type, "mcp_server_id": event.mcp_server_id, "status": event.status, "duration_ms": event.duration_ms, "occurred_at": utc(event.occurred_at)}
    fields['identity_status'] = identity_status
    fields.update(turn_id=event.turn_id, time_source=event.time_source)
    if event.turn_id:
        connection.execute('INSERT OR IGNORE INTO turns VALUES(?,?,?,?)', (key(session_key, event.turn_id), session_key, event.turn_id, fields['occurred_at']))
    connection.execute(f"INSERT INTO tool_calls({','.join(fields)}) VALUES({','.join('?' for _ in fields)})", tuple(fields.values()))
    if event.tool_type == "mcp":
        connection.execute("INSERT OR IGNORE INTO mcp_tools(server_id,tool_id,display_name) VALUES(?,?,?)", (event.mcp_server_id, event.tool_id, event.tool_name))
    connection.execute("INSERT INTO event_inbox(event_key,type,received_at,status) VALUES(?,?,?,?) ON CONFLICT(event_key) DO UPDATE SET status='done',error_code=NULL", (event_key, "tool", now(), "done"))
    return True
