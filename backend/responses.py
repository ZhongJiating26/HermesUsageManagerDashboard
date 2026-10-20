from typing import Literal

from pydantic import BaseModel

from .schemas import Envelope


class Capabilities(BaseModel):
    storage: Literal['ready', 'unavailable']
    collection: Literal['unavailable', 'registered', 'observed', 'degraded']
    hermes_runtime: Literal['unverified']
    business_api: bool


class Health(BaseModel):
    status: Literal['ok']
    plugin: Literal['hermes-usage-manager']
    version: Literal['0.6.0']
    milestone: Literal['M4']
    data_source: Literal['mock', 'live']
    capabilities: Capabilities


class Totals(BaseModel):
    input: int | None
    cached: int | None
    output: int | None


class KPI(Totals):
    total_tokens: int | None
    cost: float | None
    input_cost: float | None
    cached_cost: float | None
    output_cost: float | None
    active: int
    unknown_cost: int
    unknown_cache: int
    primary_model: str | None
    successful_requests: int
    failed_requests: int
    auxiliary_requests: int
    unresolved_sessions: int


class Day(Totals):
    day: str
    total_tokens: int | None
    active: int
    calls: int


class Distribution(Totals):
    id: str
    name: str
    tokens: int | None
    cost: float | None


class Tool(BaseModel):
    id: str
    name: str
    server_id: str
    tool_id: str
    calls: int
    failed: int
    duration_ms: int | None


class Analytics(BaseModel):
    count: int
    kpis: KPI
    trend: list[Day]
    distributions: dict[str, list[Distribution]]
    tools: list[Tool]


class AnalyticsEnvelope(Envelope):
    data: Analytics


class KPIEnvelope(Envelope):
    data: KPI


class TrendEnvelope(Envelope):
    data: list[Day]


class DistributionEnvelope(Envelope):
    data: list[Distribution]


class ToolsEnvelope(Envelope):
    data: list[Tool]
