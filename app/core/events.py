"""Trace bus + per-run emitter. Every step emits span/log/finding/containment/verdict/status
events. The bus fans out to live SSE subscribers; the full trace
lives in the repository for replay."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from app.schemas import Event, Finding, Verdict, utcnow

TERMINAL_STATUS = {"completed", "failed", "cancelled"}


class TraceBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[Event]]] = defaultdict(set)

    def subscribe(self, run_id: str) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
        self._subs[run_id].add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[Event]) -> None:
        self._subs[run_id].discard(q)

    async def publish(self, event: Event) -> None:
        for q in list(self._subs.get(event.run_id, ())):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow consumer; the full trace is replayable from the repository


class RunTrace:
    """Emits ordered events for one run. Seq starts at 1 and is unique per run."""

    def __init__(self, repo, bus: TraceBus, run_id: str):
        self._repo = repo
        self._bus = bus
        self._run_id = run_id
        self._seq = 0
        self._spans: dict[str, float] = {}

    async def _emit(self, type_: str, name: str, **data) -> None:
        self._seq += 1
        event = Event(
            run_id=self._run_id, seq=self._seq, ts=utcnow(), type=type_, name=name, data=data
        )
        self._repo.append_event(self._run_id, event)
        await self._bus.publish(event)

    async def span_start(self, name: str, *, key: str | None = None, **data) -> None:
        self._spans[key or name] = time.monotonic()
        if key is not None:
            data = {"span_key": key, **data}
        await self._emit("span_start", name, **data)

    async def span_end(self, name: str, *, key: str | None = None, error: str | None = None, **data) -> None:
        started = self._spans.pop(key or name, time.monotonic())
        duration_ms = round((time.monotonic() - started) * 1000, 1)
        if key is not None:
            data = {"span_key": key, **data}
        await self._emit("span_end", name, duration_ms=duration_ms, error=error, **data)

    async def log(self, name: str, **data) -> None:
        await self._emit("log", name, **data)

    async def finding(self, f: Finding) -> None:
        await self._emit(
            "finding",
            f.category.value,
            id=f.id,
            title=f.title,
            confidence=f.confidence,
            severity=f.severity.value,
            evidence=[ev.model_dump() for ev in f.evidence],
        )

    async def containment(self, name: str, detail: str = "", ref: str | None = None) -> None:
        await self._emit("containment", name, detail=detail, ref=ref)

    async def verdict(self, v: Verdict) -> None:
        await self._emit(
            "verdict",
            v.label.value,
            confidence=v.confidence,
            route=v.route.value,
            summary=v.summary,
            reasons=v.reasons,
            cited=v.cited_findings,
        )

    async def status(self, name: str) -> None:
        await self._emit("status", name)
