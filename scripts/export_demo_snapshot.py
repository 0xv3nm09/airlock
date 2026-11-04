"""Export the public snapshot for the static GitHub Pages demo of the web app.

Reads the real store through the same repository methods the API routes use, so every
shape matches the live API byte-for-byte (repo.stats(), repo.recent_demo(), records,
events, eval_results/latest.json, eval_cases/cases.yaml). API keys are never exported.

Usage:  python scripts/export_demo_snapshot.py   (from the repo root)
Writes: web/demo/airlock-snapshot.json — commit it; the Pages workflow builds the web
        app against it with NEXT_PUBLIC_DEMO_MODE=1.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.core.config import Settings  # noqa: E402
from app.services import build_services  # noqa: E402

OUT_PATH = REPO_ROOT / "web" / "demo" / "airlock-snapshot.json"


def load_benchmark_cases() -> list[dict]:
    import yaml

    raw = yaml.safe_load((REPO_ROOT / "eval_cases" / "cases.yaml").read_text())["cases"]
    return [
        {"name": str(c["name"]), "url": str(c["url"]), "expected": str(c["expected_verdict"])}
        for c in raw
    ]


def main() -> None:
    settings = Settings()
    svc = build_services(settings)
    llm_name = getattr(svc.llm, "name", "unknown")
    sandbox_name = getattr(svc.sandbox, "name", "unknown")
    policy_version = svc.policy.version

    records = list(svc.repo._runs.values())  # noqa: SLF001 — exporter is repo-internal tooling
    records.sort(key=lambda r: r.out.created_at)
    runs = [r.out.model_dump(mode="json") for r in records]
    traces = {r.out.id: [e.model_dump(mode="json") for e in r.events] for r in records}

    stats = {
        **svc.repo.stats(),
        "policy_version": policy_version,
        "llm": llm_name,
        "sandbox": sandbox_name,
        # Each completed run created at least one sandbox; the live counter starts at 0
        # per boot, so the honest aggregate for a static snapshot is the run count.
        "sandboxes_created": len(runs),
        "uptime_s": 0,
    }
    readyz = {
        "status": "ok",
        "llm": llm_name,
        "sandbox": sandbox_name,
        "policy_version": policy_version,
        "queue_depth": 0,
        "kill_switch": False,
    }

    bench_path = REPO_ROOT / "eval_results" / "latest.json"
    benchmark = json.loads(bench_path.read_text()) if bench_path.exists() else None

    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(),
        "readyz": readyz,
        "stats": stats,
        "runs": runs,
        "recent": svc.repo.recent_demo(25),
        "traces": traces,
        "benchmark": benchmark,
        "benchmark_cases": load_benchmark_cases(),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(snapshot, indent=1) + "\n")
    size_kb = OUT_PATH.stat().st_size // 1024
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)} ({size_kb} KB): {len(runs)} runs, "
          f"{sum(len(t) for t in traces.values())} events, "
          f"mode {llm_name}/{sandbox_name}, benchmark={'yes' if benchmark else 'no'}")


if __name__ == "__main__":
    main()
