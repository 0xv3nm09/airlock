"""FastAPI app factory + lifespan. The API only queues work; workers run the reviews."""
from __future__ import annotations

import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.agents.orchestrator import execute_run
from app.api.routes import router
from app.core.config import Settings, check_prod
from app.core.errors import AirlockError
from app.schemas import RunStatus
from app.services import build_services

# Stable in dev so the browser's stored key (localStorage + session cookie) survives
# restarts — a random-per-boot key silently invalidated Review/Dashboard every redeploy.
# Prod requires AIRLOCK_BOOTSTRAP_ADMIN_KEY (check_prod refuses the dev default).
DEV_ADMIN_KEY = "airlock-dev-admin-key"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.env == "prod":
            check_prod(settings)
        svc = build_services(settings)
        svc.dev_admin_key = settings.bootstrap_admin_key or (
            DEV_ADMIN_KEY if settings.env == "dev" else secrets.token_urlsafe(24)
        )

        async def mark_cancelled(run_id: str) -> None:
            record = svc.repo.get_record(run_id)
            if record is not None and record.out.status is RunStatus.queued:
                await svc.repo.set_status(run_id, RunStatus.cancelled, finished=True)

        svc.queue.start(
            settings.worker_concurrency,
            runner=lambda run_id, pr_url: execute_run(svc, run_id, pr_url),
            on_cancel=mark_cancelled,
        )
        app.state.services = svc
        if settings.env == "dev":
            print(
                f"[airlock] dev admin API key: {svc.dev_admin_key} (stable in dev; "
                "set AIRLOCK_BOOTSTRAP_ADMIN_KEY in prod)"
            )  # noqa: T201
        yield
        await svc.queue.stop()
        await svc.repo.flush()  # durability: write any coalesced store changes on shutdown

    app = FastAPI(title="Airlock", version="0.1.0", lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(AirlockError)
    async def airlock_error_handler(request: Request, exc: AirlockError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code,
                "message": exc.message,
                "request_id": secrets.token_hex(8),
                "details": [],
            },
        )

    return app


app = create_app()
