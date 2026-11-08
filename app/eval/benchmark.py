"""Seeded benchmark runner: every case from cases.yaml through the full pipeline.
In dummy mode this proves the harness; on the VM the same URLs point at real repos.
Usage: python -m app.eval.benchmark eval_cases/cases.yaml"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import yaml

from app.agents.orchestrator import execute_run
from app.core.config import Settings
from app.schemas import VerdictLabel
from app.services import build_services


async def run_benchmark(cases_path: str) -> int:
    cases = yaml.safe_load(Path(cases_path).read_text())["cases"]
    svc = build_services(Settings())
    rows: list[dict] = []

    for case in cases:
        t0 = time.monotonic()
        run = await svc.repo.create_run(owner_id="bench", pr_url=case["url"], policy_version=svc.policy.version)
        await execute_run(svc, run.id, case["url"])
        record = svc.repo.get_record(run.id)
        assert record is not None
        out = record.out
        duration = time.monotonic() - t0
        got = out.verdict.label.value if out.verdict else (out.status.value if out.status else "none")
        expected = case["expected_verdict"]
        actual_cats = {f.category.value for f in out.findings}
        expected_cats = set(case.get("expected_findings", []))
        rows.append(
            {
                "name": case["name"],
                "got": got,
                "expected": expected,
                "verdict_ok": got == expected,
                "findings_ok": expected_cats <= actual_cats,
                "duration_s": round(duration, 2),
                "findings": sorted(actual_cats),
                # real per-case token spend from the executed run (surfaced in the UI)
                "tokens": out.usage.prompt_tokens + out.usage.completion_tokens,
                "llm_calls": out.usage.llm_calls,
            }
        )

    _print_table(rows)
    metrics = _metrics(rows)
    print("\nMetrics:", metrics)  # noqa: T201
    all_ok = all(r["verdict_ok"] and r["findings_ok"] for r in rows)
    print(f"\n{'PASS' if all_ok else 'FAIL'}: {sum(r['verdict_ok'] for r in rows)}/{len(rows)} verdicts match")  # noqa: T201
    _save_results(rows, metrics, all_ok, f"{svc.settings.llm_provider}/{svc.settings.sandbox_backend}")
    return 0 if all_ok else 1


def _save_results(rows: list[dict], metrics: dict, all_ok: bool, mode: str) -> None:
    """Persist results for GET /v1/benchmark/latest (the benchmark screen). The mode is
    stamped so dummy numbers can never be mistaken for VM results."""
    import json
    from datetime import datetime, timezone

    out_dir = Path(__file__).resolve().parents[2] / "eval_results"
    out_dir.mkdir(exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "all_ok": all_ok,
        "metrics": metrics,
        "rows": rows,
    }
    (out_dir / "latest.json").write_text(json.dumps(payload, indent=2))


def _print_table(rows: list[dict]) -> None:
    print(f"{'case':<22} {'got':<15} {'expected':<15} {'ok':<4} {'findings_ok':<11} {'s':>5}")  # noqa: T201
    for r in rows:
        print(  # noqa: T201
            f"{r['name']:<22} {r['got']:<15} {r['expected']:<15} "
            f"{'✓' if r['verdict_ok'] else '✗':<4} {'✓' if r['findings_ok'] else '✗':<11} {r['duration_s']:>5}"
        )


def _metrics(rows: list[dict]) -> dict:
    labels = ["safe_to_merge", "needs_changes", "suspicious", "inconclusive"]
    f1s: list[float] = []
    for label in labels:
        tp = sum(1 for r in rows if r["got"] == label and r["expected"] == label)
        fp = sum(1 for r in rows if r["got"] == label and r["expected"] != label)
        fn = sum(1 for r in rows if r["got"] != label and r["expected"] == label)
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    suspicious_expected = [r for r in rows if r["expected"] == VerdictLabel.suspicious.value]
    suspicious_caught = [r for r in suspicious_expected if r["got"] == VerdictLabel.suspicious.value]
    return {
        "macro_f1": round(sum(f1s) / len(f1s), 3),
        "recall_suspicious": f"{len(suspicious_caught)}/{len(suspicious_expected)}",
        "escalation_rate": f"{sum(1 for r in rows if r['got'] == VerdictLabel.suspicious.value)}/{len(rows)} suspicious",
        "p50_duration_s": sorted(r["duration_s"] for r in rows)[len(rows) // 2],
    }


def main() -> None:
    cases_path = sys.argv[1] if len(sys.argv) > 1 else "eval_cases/cases.yaml"
    sys.exit(asyncio.run(run_benchmark(cases_path)))


if __name__ == "__main__":
    main()
