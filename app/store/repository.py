"""Repository: the in-memory store with optional SQLite write-through persistence
(`AIRLOCK_DB_PATH`). Every lookup goes through the owner filter in one place — OWASP API1,
broken object-level authorisation. Demo runs are public-read; other users' runs return
not_found so IDs don't leak.

Persistence (Oct 31): runs, findings, events and API keys survive backend restarts via a
coalesced write-through snapshot — the permanent fix for "data vanishes between runs".
Ticket T08 later swaps this engine for Postgres via SQLAlchemy; the repository API stays.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas import (
    ContainmentCounters,
    Event,
    Finding,
    IntentAssessment,
    RunOut,
    RunStatus,
    Usage,
    Verdict,
    utcnow,
)


def new_run_id() -> str:
    return "run_" + secrets.token_hex(6)


@dataclass
class RunRecord:
    out: RunOut
    events: list[Event] = field(default_factory=list)
    _finding_seq: int = 0


class InMemoryRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._keys: dict[str, dict] = {}
        self._db_path = db_path or None
        self._flush_task: asyncio.Task | None = None
        if self._db_path:
            self._load()

    # --- persistence (SQLite write-through, coalesced) ---------------------
    def _load(self) -> None:
        path = Path(self._db_path)  # type: ignore[arg-type]
        if not path.exists():
            return
        conn = sqlite3.connect(path)
        try:
            row = conn.execute("SELECT v FROM store WHERE k = 'state'").fetchone()
        finally:
            conn.close()
        if not row:
            return
        state = json.loads(row[0])
        for run_id, r in state.get("runs", {}).items():
            events = [Event.model_validate(e) for e in r.get("events", [])]
            record = RunRecord(out=RunOut.model_validate(r["out"]), events=events)
            ids = [int(f.id[1:]) for f in record.out.findings if f.id.startswith("F")]
            record._finding_seq = max(ids, default=0)
            self._runs[run_id] = record
        self._keys = state.get("keys", {})

    def _schedule_persist(self) -> None:
        if not self._db_path:
            return
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.get_event_loop().create_task(self._flush_soon())

    async def _flush_soon(self) -> None:
        await asyncio.sleep(0.25)  # coalesce bursts of mutations into one write
        await self.flush()

    async def flush(self) -> None:
        if not self._db_path:
            return
        state = {
            "runs": {
                run_id: {
                    "out": record.out.model_dump(mode="json"),
                    "events": [e.model_dump(mode="json") for e in record.events],
                }
                for run_id, record in self._runs.items()
            },
            "keys": self._keys,
        }
        payload = json.dumps(state)

        def _write() -> None:
            conn = sqlite3.connect(self._db_path or "")
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS store (k TEXT PRIMARY KEY, v TEXT)")
                conn.execute(
                    "INSERT OR REPLACE INTO store (k, v) VALUES ('state', ?)", (payload,)
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_write)

    # --- lifecycle --------------------------------------------------------
    async def create_run(self, *, owner_id: str, pr_url: str, policy_version: str, is_demo: bool = False) -> RunOut:
        out = RunOut(
            id=new_run_id(),
            owner_id=owner_id,
            is_demo=is_demo,
            status=RunStatus.queued,
            pr_url=pr_url,
            policy_version=policy_version,
        )
        self._runs[out.id] = RunRecord(out=out)
        self._schedule_persist()
        return out

    def get_record(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def get_for_principal(self, run_id: str, owner_id: str | None) -> RunOut | None:
        """owner_id None = anonymous (demo runs only). Anyone else sees only their own."""
        record = self._runs.get(run_id)
        if record is None:
            return None
        if record.out.is_demo:
            return record.out
        if owner_id is None or record.out.owner_id != owner_id:
            return None
        return record.out

    def list_for(self, owner_id: str) -> list[RunOut]:
        return [r.out for r in self._runs.values() if r.out.owner_id == owner_id]

    def list_all(self) -> list[RunOut]:
        return [r.out for r in self._runs.values()]

    # --- API keys (workbook spec: POST /v1/admin/keys) — hash stored, plain shown once ---
    def create_api_key(self, key_id: str, owner_id: str, secret_hash: str, scopes: list[str]) -> None:
        self._keys[key_id] = {
            "owner_id": owner_id,
            "secret_hash": secret_hash,
            "scopes": list(scopes),
            "revoked": False,
            "created_at": utcnow().isoformat(),
        }
        self._schedule_persist()

    def get_api_key(self, key_id: str) -> dict | None:
        record = self._keys.get(key_id)
        return dict(record) if record else None

    def revoke_api_key(self, key_id: str) -> bool:
        record = self._keys.get(key_id)
        if record is None:
            return False
        record["revoked"] = True
        self._schedule_persist()
        return True

    def list_api_keys(self) -> list[dict]:
        out = []
        for key_id, record in self._keys.items():
            out.append(
                {
                    "key_id": key_id,
                    "owner_id": record["owner_id"],
                    "scopes": record["scopes"],
                    "revoked": record["revoked"],
                    "created_at": record["created_at"],
                }
            )
        return sorted(out, key=lambda k: k["created_at"], reverse=True)

    # --- aggregate stats (public console/home, demo-scope data only) --------
    def stats(self) -> dict:
        runs = [r.out for r in self._runs.values()]
        completed = [r for r in runs if r.status is RunStatus.completed]
        verdicts = {"suspicious": 0, "needs_changes": 0, "safe_to_merge": 0, "inconclusive": 0}
        for r in completed:
            if r.verdict is not None:
                verdicts[r.verdict.label.value] = verdicts.get(r.verdict.label.value, 0) + 1
        tokens = sum(r.usage.prompt_tokens + r.usage.completion_tokens for r in runs)
        llm_calls = sum(r.usage.llm_calls for r in runs)
        contained = sum(
            r.counters.network_blocked + r.counters.canary_hits + r.counters.writes_denied + r.counters.limits_hit
            for r in runs
        )
        return {
            "runs_total": len(runs),
            "runs_completed": len(completed),
            "suspicious": verdicts["suspicious"],
            "needs_changes": verdicts["needs_changes"],
            "safe_to_merge": verdicts["safe_to_merge"],
            "inconclusive": verdicts["inconclusive"],
            "attacks_contained": contained,
            "tokens_total": tokens,
            "llm_calls_total": llm_calls,
            "avg_tokens_per_run": round(tokens / len(runs)) if runs else 0,
        }

    def recent_demo(self, limit: int = 10) -> list[dict]:
        """Public feed: demo runs only (never other owners' runs), newest first, with the
        containment events that fired — the console's terminal feed is built from these."""
        demos = [r for r in self._runs.values() if r.out.is_demo]
        demos.sort(key=lambda r: r.out.created_at, reverse=True)
        out: list[dict] = []
        for record in demos[:limit]:
            o = record.out
            containment = [
                {"name": e.name, "detail": str(e.data.get("detail", "")), "ts": e.ts.isoformat()}
                for e in record.events
                if e.type == "containment"
            ][-6:]
            out.append(
                {
                    "id": o.id,
                    "pr_url": o.pr_url,
                    "status": o.status.value,
                    "verdict": o.verdict.label.value if o.verdict else None,
                    "confidence": o.verdict.confidence if o.verdict else None,
                    "counters": o.counters.model_dump(),
                    "usage": o.usage.model_dump(),
                    "created_at": o.created_at.isoformat(),
                    "containment": containment,
                }
            )
        return out

    # --- mutations --------------------------------------------------------
    async def set_status(self, run_id: str, status: RunStatus, *, error: str | None = None, finished: bool = False) -> None:
        record = self._runs.get(run_id)
        if record is None:
            return
        self._schedule_persist()
        record.out.status = status
        if error is not None:
            record.out.error = error
        if finished:
            record.out.finished_at = utcnow()

    async def add_finding(self, run_id: str, finding: Finding) -> Finding:
        record = self._runs[run_id]
        record._finding_seq += 1
        finding.id = f"F{record._finding_seq}"
        record.out.findings.append(finding)
        self._schedule_persist()
        return finding

    async def set_verdict(self, run_id: str, verdict: Verdict) -> None:
        record = self._runs.get(run_id)
        if record:
            record.out.verdict = verdict
            self._schedule_persist()

    async def set_intent(self, run_id: str, intent: IntentAssessment | None) -> None:
        record = self._runs.get(run_id)
        if record:
            record.out.intent = intent
            self._schedule_persist()

    async def set_counters(self, run_id: str, counters: ContainmentCounters) -> None:
        record = self._runs.get(run_id)
        if record:
            record.out.counters = counters
            self._schedule_persist()

    async def set_decision(self, run_id: str, decision: str, note: str, decided_by: str) -> None:
        record = self._runs.get(run_id)
        if record:
            record.out.human_decision = decision  # type: ignore[assignment]
            record.out.human_note = note
            record.out.decided_by = decided_by
            record.out.decided_at = utcnow()
            self._schedule_persist()

    async def add_usage(self, run_id: str, prompt: int, completion: int, calls: int) -> None:
        record = self._runs.get(run_id)
        if record:
            u = record.out.usage
            record.out.usage = Usage(
                prompt_tokens=u.prompt_tokens + prompt,
                completion_tokens=u.completion_tokens + completion,
                llm_calls=u.llm_calls + calls,
            )
            self._schedule_persist()

    # --- events -----------------------------------------------------------
    def append_event(self, run_id: str, event: Event) -> None:
        record = self._runs.get(run_id)
        if record is not None:
            record.events.append(event)
            self._schedule_persist()

    def get_events(self, run_id: str) -> list[Event]:
        record = self._runs.get(run_id)
        return list(record.events) if record else []
