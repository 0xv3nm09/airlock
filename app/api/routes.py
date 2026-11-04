"""API routes: health, demo runs (no login), runs CRUD, live SSE timeline, trace, review
decisions, benchmark results, cookie sessions, public stats."""
from __future__ import annotations

import hmac
import json
import time
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import SESSION_COOKIE, Principal, get_services, optional_principal, require
from app.core.config import REPO_ROOT
from app.core.errors import NotFound, Unauthorized, ValidationFailed
from app.core.events import TERMINAL_STATUS
from app.schemas import (
    ApiKeyCreate,
    ApiKeyInfo,
    ApiKeyOut,
    DecisionCreate,
    DemoRunCreate,
    Event,
    RunCreate,
    RunOut,
    RunStatus,
    SessionCreate,
)
from app.services import Services
from app.sources.dummy import DEMO_SCENARIOS

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(svc: Annotated[Services, Depends(get_services)]) -> dict:
    return {
        "status": "ok",
        "llm": getattr(svc.llm, "name", "unknown"),
        "sandbox": getattr(svc.sandbox, "name", "unknown"),
        "policy_version": svc.policy.version,
        "queue_depth": svc.queue.depth(),
        "kill_switch": False,
    }


@router.post("/v1/auth/session")
async def create_session(
    body: SessionCreate, svc: Annotated[Services, Depends(get_services)]
) -> JSONResponse:
    """Exchange an API key for an HttpOnly cookie session (60 min). EventSource cannot send
    headers, so the live timeline for owner runs depends on this cookie."""
    if not hmac.compare_digest(body.api_key, svc.dev_admin_key):
        raise Unauthorized("invalid API key")
    response = JSONResponse({"ok": True})
    response.set_cookie(
        SESSION_COOKIE,
        body.api_key,
        httponly=True,
        samesite="strict",
        max_age=3600,
        secure=svc.settings.env == "prod",
    )
    return response


def _is_trusted_proxy(host: str) -> bool:
    import ipaddress

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def _client_ip_for_limit(request: Request) -> str:
    """Rate-limit key. X-Forwarded-For is honored ONLY when the direct peer is our own
    proxy (loopback/private), and we take the LAST hop — the one our proxy appended.
    A client-supplied first hop is spoofable and resets nothing (Oct 29 audit fix)."""
    direct = request.client.host if request.client else "anonymous"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and _is_trusted_proxy(direct):
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return direct


@router.post("/v1/demo/runs", status_code=202, response_model=RunOut)
async def create_demo_run(
    body: DemoRunCreate, request: Request, svc: Annotated[Services, Depends(get_services)]
) -> RunOut:
    svc.ratelimit.check(f"demo:{_client_ip_for_limit(request)}", svc.settings.rate_limit_demo_per_min)
    pr_url = DEMO_SCENARIOS[body.scenario]
    run = await svc.repo.create_run(
        owner_id="demo", pr_url=pr_url, policy_version=svc.policy.version, is_demo=True
    )
    await svc.queue.enqueue(run.id, pr_url)
    return run


@router.post("/v1/runs", status_code=202, response_model=RunOut)
async def create_run(
    body: RunCreate,
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal = Depends(require("runs:write")),
) -> RunOut:
    svc.ratelimit.check(f"runs:{principal.owner}", svc.settings.rate_limit_runs_per_min)
    from app.guardrails.input import parse_pr_url

    parse_pr_url(body.pr_url)  # 422 invalid_pr_url on bad input
    run = await svc.repo.create_run(
        owner_id=principal.owner, pr_url=body.pr_url, policy_version=svc.policy.version
    )
    await svc.queue.enqueue(run.id, body.pr_url)
    return run


@router.get("/v1/runs", response_model=list[RunOut])
async def list_runs(
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal = Depends(require("runs:read")),
) -> list[RunOut]:
    if "admin" in principal.scopes:
        return svc.repo.list_all()
    return svc.repo.list_for(principal.owner)


@router.post("/v1/admin/keys", response_model=ApiKeyOut, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal = Depends(require("admin")),
) -> ApiKeyOut:
    """Issue a team key: full secret returned ONCE, only the SHA-256 hash is stored.
    The `admin` scope is never grantable here — maker-checker stays intact."""
    import hashlib
    import secrets as pysecrets

    key_id = "ak_" + pysecrets.token_hex(4)
    secret = pysecrets.token_urlsafe(24)
    full_key = f"{key_id}.{secret}"
    svc.repo.create_api_key(
        key_id,
        body.owner_id,
        hashlib.sha256(full_key.encode()).hexdigest(),
        list(body.scopes),
    )
    return ApiKeyOut(key_id=key_id, key=full_key, owner_id=body.owner_id, scopes=list(body.scopes))


@router.get("/v1/admin/keys", response_model=list[ApiKeyInfo])
async def list_api_keys(
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal = Depends(require("admin")),
) -> list[ApiKeyInfo]:
    return [ApiKeyInfo(**k) for k in svc.repo.list_api_keys()]


@router.post("/v1/admin/keys/{key_id}/revoke", response_model=ApiKeyInfo)
async def revoke_api_key(
    key_id: str,
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal = Depends(require("admin")),
) -> ApiKeyInfo:
    if not svc.repo.revoke_api_key(key_id):
        raise NotFound("key not found")
    record = svc.repo.get_api_key(key_id)
    assert record is not None
    return ApiKeyInfo(
        key_id=key_id,
        owner_id=record["owner_id"],
        scopes=record["scopes"],
        revoked=record["revoked"],
        created_at=record["created_at"],
    )


@router.post("/v1/demo/seed-library", status_code=202)
async def seed_demo_library(
    request: Request, svc: Annotated[Services, Depends(get_services)]
) -> dict:
    """One click fills the Dashboard: enqueue every case in the attack library as real
    demo runs. Rate-limited hard — on the VM with real models this spends credits."""
    svc.ratelimit.check("seed-library", 2)  # 2×/min — 19 runs each time
    cases = _load_cases()
    run_ids: list[str] = []
    for name, pr_url in cases.items():
        run = await svc.repo.create_run(
            owner_id="demo", pr_url=pr_url, policy_version=svc.policy.version, is_demo=True
        )
        await svc.queue.enqueue(run.id, pr_url)
        run_ids.append(run.id)
    return {"enqueued": len(run_ids), "run_ids": run_ids}


@router.get("/v1/runs/recent")
async def recent_runs(
    svc: Annotated[Services, Depends(get_services)], limit: int = 10
) -> list[dict]:
    """Public feed of demo runs only — other owners' runs are never exposed here.
    Registered BEFORE /v1/runs/{run_id} so `recent` is not captured as an id."""
    return svc.repo.recent_demo(max(1, min(limit, 25)))


@router.get("/v1/runs/{run_id}", response_model=RunOut)
async def get_run(
    run_id: str,
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal | None = Depends(optional_principal),
) -> RunOut:
    out = svc.repo.get_for_principal(run_id, principal.owner if principal else None)
    if out is None:
        raise NotFound("run not found")
    record = svc.repo.get_record(run_id)
    if record and record.out.intent is not None:
        out.intent = record.out.intent
    return out


@router.get("/v1/runs/{run_id}/events")
async def stream_events(
    run_id: str,
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal | None = Depends(optional_principal),
) -> StreamingResponse:
    record = svc.repo.get_record(run_id)
    allowed = record is not None and (
        record.out.is_demo or (principal is not None and record.out.owner_id == principal.owner)
    )
    if not allowed:
        raise NotFound("run not found")

    async def gen():
        q = svc.bus.subscribe(run_id)
        last_seq = 0
        try:
            terminal_seen = False
            for event in svc.repo.get_events(run_id):
                last_seq = max(last_seq, event.seq)
                if event.type == "status" and event.name in TERMINAL_STATUS:
                    terminal_seen = True
                yield _sse(event)
            if terminal_seen:
                return  # finished run: the replay closes the stream, no live wait
            while True:
                event = await q.get()
                if event.seq <= last_seq:
                    continue
                yield _sse(event)
                if event.type == "status" and event.name in TERMINAL_STATUS:
                    break
        finally:
            svc.bus.unsubscribe(run_id, q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/v1/runs/{run_id}/trace", response_model=list[Event])
async def get_trace(
    run_id: str,
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal | None = Depends(optional_principal),
) -> list[Event]:
    record = svc.repo.get_record(run_id)
    allowed = record is not None and (
        record.out.is_demo or (principal is not None and record.out.owner_id == principal.owner)
    )
    if not allowed:
        raise NotFound("run not found")
    return svc.repo.get_events(run_id)


@router.post("/v1/runs/{run_id}/decision", response_model=RunOut)
async def decide_run(
    run_id: str,
    body: DecisionCreate,
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal = Depends(require("runs:approve")),
) -> RunOut:
    out = svc.repo.get_for_principal(run_id, principal.owner)
    if out is None:
        raise NotFound("run not found")
    if out.status is not RunStatus.completed or out.verdict is None:
        raise ValidationFailed("only completed runs with a verdict can be decided")
    await svc.repo.set_decision(run_id, body.decision, body.note, principal.owner)
    record = svc.repo.get_record(run_id)
    assert record is not None
    return record.out


@router.get("/v1/stats")
async def stats(svc: Annotated[Services, Depends(get_services)]) -> dict:
    """Public aggregate numbers for the home page and console (no per-owner data)."""
    return {
        **svc.repo.stats(),
        "policy_version": svc.policy.version,
        "llm": getattr(svc.llm, "name", "unknown"),
        "sandbox": getattr(svc.sandbox, "name", "unknown"),
        "sandboxes_created": getattr(svc.sandbox, "created", 0),
        "uptime_s": int(time.monotonic() - svc.started_at),
    }


@router.get("/v1/benchmark/latest")
async def benchmark_latest() -> dict:
    path = REPO_ROOT / "eval_results" / "latest.json"
    if not path.exists():
        raise NotFound("no benchmark results yet; run `make bench`")
    return cast(dict, json.loads(path.read_text()))


def _load_cases() -> dict[str, str]:
    import yaml

    raw = yaml.safe_load((REPO_ROOT / "eval_cases" / "cases.yaml").read_text())["cases"]
    return {str(c["name"]): str(c["url"]) for c in raw}


@router.get("/v1/benchmark/cases")
async def benchmark_cases() -> list[dict]:
    """The seeded attack library, open to everyone: name, PR url, expected verdict."""
    import yaml

    raw = yaml.safe_load((REPO_ROOT / "eval_cases" / "cases.yaml").read_text())["cases"]
    return [
        {"name": str(c["name"]), "url": str(c["url"]), "expected": str(c["expected_verdict"])}
        for c in raw
    ]


@router.post("/v1/benchmark/run/{name}", status_code=202, response_model=RunOut)
async def benchmark_case_run(
    name: str,
    request: Request,
    svc: Annotated[Services, Depends(get_services)],
) -> RunOut:
    """Run one library case live and return a real (demo-scope) run the caller can open:
    full timeline, receipts, sandbox logs and per-run token usage. Public like the demo
    buttons and bound to the same per-IP budget — on the VM this spends LLM credits."""
    svc.ratelimit.check(f"bench:{_client_ip_for_limit(request)}", svc.settings.rate_limit_demo_per_min)
    cases = _load_cases()
    if name not in cases:
        raise NotFound(f"unknown benchmark case: {name}")
    pr_url = cases[name]
    run = await svc.repo.create_run(
        owner_id="demo", pr_url=pr_url, policy_version=svc.policy.version, is_demo=True
    )
    await svc.queue.enqueue(run.id, pr_url)
    return run


@router.post("/v1/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(
    run_id: str,
    svc: Annotated[Services, Depends(get_services)],
    principal: Principal = Depends(require("runs:write")),
) -> RunOut:
    out = svc.repo.get_for_principal(run_id, principal.owner)
    if out is None:
        raise NotFound("run not found")
    svc.queue.cancel(run_id)
    return out


def _sse(event) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
