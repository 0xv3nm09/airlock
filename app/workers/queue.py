"""In-process asyncio queue with N worker tasks (MVP). Swap to arq + Valkey later via the
same enqueue() interface."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.core.errors import QueueFull

log = logging.getLogger("airlock.queue")

Runner = Callable[[str, str], Awaitable[None]]


CancelCallback = Callable[[str], Awaitable[None]]


class InProcessQueue:
    def __init__(self, maxsize: int = 100):
        self._q: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=maxsize)
        self._workers: list[asyncio.Task] = []
        self._cancelled: dict[str, asyncio.Event] = {}
        self._runner: Runner | None = None
        self._on_cancel: CancelCallback | None = None

    def start(self, concurrency: int, runner: Runner, on_cancel: CancelCallback | None = None) -> None:
        self._runner = runner
        self._on_cancel = on_cancel
        for i in range(concurrency):
            self._workers.append(asyncio.create_task(self._work(i)))

    async def enqueue(self, run_id: str, pr_url: str) -> None:
        try:
            self._q.put_nowait((run_id, pr_url))
        except asyncio.QueueFull as e:
            raise QueueFull("queue is full; try again shortly") from e

    def cancel(self, run_id: str) -> None:
        self._cancelled.setdefault(run_id, asyncio.Event()).set()

    def is_cancelled(self, run_id: str) -> bool:
        ev = self._cancelled.get(run_id)
        return bool(ev and ev.is_set())

    def depth(self) -> int:
        return self._q.qsize()

    async def _work(self, i: int) -> None:
        assert self._runner is not None
        while True:
            run_id, pr_url = await self._q.get()
            try:
                if self.is_cancelled(run_id):
                    # Cancelled before it started: the run must not sit in `queued` forever.
                    if self._on_cancel is not None:
                        await self._on_cancel(run_id)
                    continue
                await self._runner(run_id, pr_url)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("worker %s failed run %s", i, run_id)
            finally:
                self._q.task_done()

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
