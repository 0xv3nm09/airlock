"""API dependencies: principal from X-API-Key (session JWTs come with ticket T09),
scope enforcement, and the services accessor."""
from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Request

from app.core.errors import Forbidden, Unauthorized
from app.services import Services

ALL_SCOPES = {"runs:read", "runs:write", "runs:approve", "admin"}

# HttpOnly cookie set by POST /v1/auth/session so the browser's EventSource (which cannot
# send headers) can stream owner runs — workbook FE spec "Backend changes the frontend needs".
SESSION_COOKIE = "airlock_session"


class Principal:
    def __init__(self, owner: str, scopes: set[str]):
        self.owner = owner
        self.scopes = scopes

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise Forbidden(f"missing scope: {scope}")


def get_services(request: Request) -> Services:
    return request.app.state.services


def optional_principal(request: Request, svc: Annotated[Services, Depends(get_services)]) -> Principal | None:
    key = request.headers.get("X-API-Key") or request.cookies.get(SESSION_COOKIE, "")
    if not key:
        return None
    if hmac.compare_digest(key, svc.dev_admin_key):
        return Principal(owner="admin", scopes=set(ALL_SCOPES))
    # Team keys look like ak_<id>.<secret> — the id finds the record, the hash verifies it.
    if key.startswith("ak_"):
        import hashlib
        import re

        m = re.fullmatch(r"(ak_[0-9a-f]{8})\.(.+)", key)
        if m:
            record = svc.repo.get_api_key(m.group(1))
            if record and not record["revoked"]:
                digest = hashlib.sha256(key.encode()).hexdigest()
                if hmac.compare_digest(digest, record["secret_hash"]):
                    return Principal(owner=record["owner_id"], scopes=set(record["scopes"]))
    return None


def get_principal(
    principal: Annotated[Principal | None, Depends(optional_principal)],
) -> Principal:
    if principal is None:
        raise Unauthorized("send 'X-API-Key: <key>' (demo endpoints need no key)")
    return principal


def require(scope: str):
    async def dep(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        principal.require(scope)
        return principal

    return dep
