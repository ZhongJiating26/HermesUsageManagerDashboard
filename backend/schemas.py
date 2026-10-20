from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field, JsonValue, field_validator

from .db import utc


class Envelope(BaseModel):
    data: JsonValue
    meta: dict[str, JsonValue]


class Window:
    def __init__(self, start, end, tz, department_id="", user_id="", server_id=""):
        try:
            self.zone = ZoneInfo(tz)
            self.start = datetime.fromisoformat(start)
            self.end = datetime.fromisoformat(end)
            if self.start.tzinfo is None:
                self.start = self.start.replace(tzinfo=self.zone)
            if self.end.tzinfo is None:
                self.end = self.end.replace(tzinfo=self.zone)
            if (self.end.astimezone(self.zone).date() - self.start.astimezone(self.zone).date()).days > 366:
                raise ValueError('Too many calendar days')
            self.start, self.end = utc(self.start), utc(self.end)
            delta = datetime.fromisoformat(self.end) - datetime.fromisoformat(self.start)
            if not timedelta(0) < delta <= timedelta(days=367):
                raise ValueError("Invalid range")
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise HTTPException(422, {"code": "INVALID_WINDOW", "message": "日期范围或时区无效（最多 366 个自然日）"}) from error
        self.tz = tz
        self.department_id, self.user_id, self.server_id = department_id, user_id, server_id


def get_window(from_: str | None = Query(None, alias="from"), to: str | None = None, tz: str = "Asia/Shanghai", start: str | None = None, end: str | None = None, department_id: str = "", user_id: str = "", server_id: str = ""):
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return Window(from_ or start or str(today - timedelta(days=6)), to or end or str(today + timedelta(days=1)), tz, department_id, user_id, server_id)


class DepartmentBody(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Empty name")
        return value.strip()


class UserBody(DepartmentBody):
    external_id: str = Field(min_length=1, max_length=100)
    department_id: str
    profile: str = Field(default="", max_length=100)
    platform: str = Field(default="feishu", max_length=50)


class MoveBody(BaseModel):
    user_ids: list[str] = Field(min_length=1, max_length=100)
    department_id: str


class PriceBody(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    input: Decimal = Field(ge=0, max_digits=16, decimal_places=6, allow_inf_nan=False)
    cached: Decimal = Field(ge=0, max_digits=16, decimal_places=6, allow_inf_nan=False)
    output: Decimal = Field(ge=0, max_digits=16, decimal_places=6, allow_inf_nan=False)
    valid_from: date
    valid_to: date | None = None
    enabled: bool = True

    @field_validator("provider", "model")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Empty model/provider")
        return value.strip()


class SettingsBody(BaseModel):
    export_enabled: bool


def price_period(body, tz):
    if body.valid_to is not None and (body.valid_to < body.valid_from or body.valid_to == date.max):
        raise HTTPException(422, {"code": "INVALID_PRICE_PERIOD", "message": "价格结束日期无效或早于开始日期"})
    zone = ZoneInfo(tz)
    start = utc(datetime.combine(body.valid_from, time(), zone))
    end = utc(datetime.combine(body.valid_to + timedelta(days=1), time(), zone)) if body.valid_to else None
    return start, end
