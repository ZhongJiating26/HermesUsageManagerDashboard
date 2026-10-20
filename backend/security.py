import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Principal:
    id: str
    role: str
    department_id: str | None = None
    user_id: str | None = None


def get_principal(request: Request):
    if os.environ.get("USAGE_MANAGER_TRUST_DASHBOARD_ADMIN") != "1":
        raise HTTPException(403, {"code": "IDENTITY_UNAVAILABLE", "message": "管理员身份适配尚未显式启用"})
    from .adapters.hermes import require_dashboard_admin
    require_dashboard_admin(request)
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD") and origin and urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(403, {"code": "ORIGIN_DENIED", "message": "请求来源不匹配"})
    return Principal("hermes-dashboard-admin", "admin")


def require(principal, capability):
    permitted = {"read": {"admin", "auditor", "department", "user"}, "audit": {"admin", "auditor"}, "audit_detail": {'admin'}, "write": {"admin"}, "manage": {"admin"}}
    if principal.role not in permitted[capability] or (principal.role == "department" and not principal.department_id) or (principal.role == "user" and not principal.user_id):
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "没有此操作权限"})
