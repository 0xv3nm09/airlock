"""Composition root: build every part from Settings. Swappable via .env only."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import Settings
from app.core.errors import RateLimited
from app.core.events import TraceBus
from app.guardrails.policy import Policy
from app.llm.base import LLMClient
from app.llm.factory import build_llm
from app.preflight.osv import AgeLookup, OSVClient
from app.sandbox.base import SandboxBackend
from app.sandbox.factory import build_sandbox
from app.schemas import PRInfo
from app.store.repository import InMemoryRepository
from app.workers.queue import InProcessQueue


class PRSource(Protocol):
    name: str

    async def get_pr(self, url: str) -> "PRInfo": ...

    async def fetch_tarball(self, owner: str, repo: str, ref: str) -> bytes: ...


@dataclass
class Services:
    settings: Settings
    policy: Policy
    repo: InMemoryRepository
    bus: TraceBus
    llm: LLMClient
    sandbox: SandboxBackend
    pr_source: PRSource
    osv: OSVClient
    age_lookup: AgeLookup
    queue: InProcessQueue
    ratelimit: "SlidingWindow"
    started_at: float = field(default_factory=time.monotonic)
    dev_admin_key: str = ""


class SlidingWindow:
    """Small in-memory limiter, enough for one VM (SlowAPI + Redis when multi-process)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int) -> None:
        import time

        now = time.monotonic()
        dq = self._hits[key]
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= limit:
            raise RateLimited(f"rate limit of {limit}/min exceeded; retry later")
        dq.append(now)


def build_services(settings: Settings) -> Services:
    from app.preflight.osv import DummyAgeLookup, DummyOSV, HttpxAgeLookup, HttpxOSV
    from app.sources.dummy import DummyPRSource
    from app.sources.github import GitHubSource

    policy = Policy.load(settings.policy_path)
    llm: LLMClient = build_llm(settings)
    pr_source: PRSource
    osv: OSVClient
    age: AgeLookup
    if settings.llm_provider == "dummy":
        pr_source = DummyPRSource()
        osv = DummyOSV()
        age = DummyAgeLookup()
    else:
        pr_source = GitHubSource(settings)
        osv = HttpxOSV()
        age = HttpxAgeLookup()
    sandbox: SandboxBackend = build_sandbox(settings)
    return Services(
        settings=settings,
        policy=policy,
        repo=InMemoryRepository(db_path=settings.db_path),
        bus=TraceBus(),
        llm=llm,
        sandbox=sandbox,
        pr_source=pr_source,
        osv=osv,
        age_lookup=age,
        queue=InProcessQueue(),
        ratelimit=SlidingWindow(),
    )
