#!/usr/bin/env python3
"""Collect the full 19-case benchmark from the live Airlock VM into real-data JSON.

Runs each case once (public benchmark endpoint, per-IP rate limited — this paces itself),
waits for terminal status, then pulls run details + traces for every case. Output:
  eval_results/live-benchmark.json  — the full machine-readable bundle
Printed summary mirrors what the benchmark page shows, plus real tokens/durations.

Usage: python scripts/collect_live_results.py [--host http://139.84.176.16] [--admin-key-file ~/.vultr/prod-admin-key]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

REPO_ROOT = Path(__file__).resolve().parent.parent


def call(url: str, *, method: str = "GET", body: dict | None = None, key: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urlrequest.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **({"X-API-Key": key} if key else {})},
    )
    with urlrequest.urlopen(req, timeout=30) as r:
        return json.load(r)


def run_case(host: str, name: str, admin_key: str | None) -> dict:
    """Start one case as a demo run and wait for a terminal status."""
    started = time.time()
    out = call(f"{host}/v1/benchmark/run/{name}", method="POST", body={})
    run_id = out["id"]

    status, record = "queued", {}
    for _ in range(90):  # up to 15 min per case — real models + installs
        time.sleep(10)
        try:
            record = call(f"{host}/v1/runs/{run_id}", key=admin_key)
            status = record.get("status", "unknown")
        except urlerror.HTTPError as e:
            if e.code == 404:  # owner run without key — retry once key-less demo fetch fails
                continue
            raise
        if status in ("completed", "failed", "cancelled"):
            break

    v = record.get("verdict") or {}
    u = record.get("usage") or {}
    trace: list = []
    try:
        trace = call(f"{host}/v1/runs/{run_id}/trace", key=admin_key)
    except Exception:
        pass
    return {
        "case": name,
        "run_id": run_id,
        "status": status,
        "verdict": v.get("label"),
        "confidence": v.get("confidence"),
        "summary": v.get("summary"),
        "reasons": v.get("reasons"),
        "cited_findings": v.get("cited_findings"),
        "counters": record.get("counters"),
        "usage": u,
        "findings": [
            {
                "category": f.get("category"),
                "severity": f.get("severity"),
                "title": f.get("title"),
                "confidence": f.get("confidence"),
            }
            for f in (record.get("findings") or [])
        ],
        "human_decision": record.get("human_decision"),
        "wall_clock_s": round(time.time() - started, 1),
        "trace_events": len(trace),
        "trace": trace,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://139.84.176.16")
    ap.add_argument("--admin-key-file", default=str(Path.home() / ".vultr" / "prod-admin-key"))
    ap.add_argument("--skip-existing", action="store_true", help="keep already-collected cases")
    args = ap.parse_args()

    import yaml

    cases = yaml.safe_load((REPO_ROOT / "eval_cases" / "cases.yaml").read_text())["cases"]
    admin = None
    p = Path(args.admin_key_file)
    if p.exists():
        admin = p.read_text().strip()

    out_path = REPO_ROOT / "eval_results" / "live-benchmark.json"
    results: dict[str, dict] = {}
    if args.skip_existing and out_path.exists():
        for row in json.loads(out_path.read_text())["results"]:
            if row["status"] in ("completed", "failed"):
                results[row["case"]] = row

    rate_window: list[float] = []
    for c in cases:
        name = c["name"]
        if name in results:
            print(f"= {name}: already collected ({results[name]['status']})")
            continue
        # respect the 10/min demo budget: max 9 starts per rolling 60s
        now = time.time()
        rate_window = [t for t in rate_window if now - t < 60]
        if len(rate_window) >= 9:
            wait = 60 - (now - rate_window[0]) + 2
            print(f"  (rate limit: sleeping {wait:.0f}s)")
            time.sleep(wait)
        rate_window.append(time.time())

        print(f"> {name} (expected {c['expected_verdict']})…", flush=True)
        try:
            row = run_case(args.host, name, admin)
        except Exception as e:  # noqa: BLE001 — one failed case must not kill the sweep
            print(f"  ! {name}: collector error {e}", flush=True)
            continue
        results[name] = row
        got = row.get("verdict") or f"no-verdict({row['status']})"
        mark = "OK " if got == c["expected_verdict"] else "MISMATCH"
        print(
            f"  {mark} got={got} tokens={row['usage'].get('prompt_tokens', 0) + row['usage'].get('completion_tokens', 0)}"
            f" llm_calls={row['usage'].get('llm_calls', 0)} wall={row['wall_clock_s']}s"
        )
        # persist progress after every case so a killed sweep resumes with --skip-existing
        out_path.write_text(json.dumps({"host": args.host, "results": list(results.values())}, indent=1))

    # summary
    rows = list(results.values())
    expected = {c["name"]: c["expected_verdict"] for c in cases}
    ok = sum(1 for r in rows if (r.get("verdict") or f"no-verdict({r['status']})") == expected.get(r["case"]))
    print(f"\n=== {ok}/{len(rows)} expected-verdict matches ===")
    for r in sorted(rows, key=lambda x: x["case"]):
        got = r.get("verdict") or f"no-verdict({r['status']})"
        exp = expected.get(r["case"], "?")
        tok = r["usage"].get("prompt_tokens", 0) + r["usage"].get("completion_tokens", 0)
        print(f"  {r['case']:22} {exp:13} → {got:13} {'✓' if got == exp else '✗'} tok={tok:>6} wall={r['wall_clock_s']:>7}s")


if __name__ == "__main__":
    main()
