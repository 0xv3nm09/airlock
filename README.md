# Airlock

**Run the PR before you trust it.** Airlock runs a stranger's pull request inside a throwaway
sandbox on Vultr, watches what it does, and reports only what it proved. Entry for the
Vultr: Agent Rush Hackathon, Challenge 01 "Blast Radius Zero", Pattern A (sandboxed code
execution).

This folder is the working backend skeleton, built and verified in **dummy mode**: the whole
pipeline runs offline with a scripted LLM and sandbox, so the demo, benchmark and CI work
before a single Vultr credit is spent.

## Quickstart

```bash
cd airlock
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # dev defaults: dummy LLM, dummy sandbox, offline
make check                    # ruff + pytest
make dev                      # API on :8000 (prints a dev admin API key)
make bench                    # 17-case seeded benchmark in dummy mode
```

Try it:

```bash
KEY=<the dev key printed at startup>
curl -s localhost:8000/readyz
curl -s -X POST localhost:8000/v1/demo/runs -H 'Content-Type: application/json' \
     -d '{"scenario": "malicious"}'
curl -s localhost:8000/v1/runs/<run_id>
curl -N localhost:8000/v1/runs/<run_id>/events   # live SSE timeline
```

## What works today (dummy mode)

- Full review pipeline: screen → pre-flight (OSV MAL- check, injection scan, static risk) →
  plan → two sandboxes (base vs PR) → install with self-heal → tests → generated tests →
  behaviour scan → deterministic verdict → summary with cite-check → guaranteed cleanup.
- 17 scripted scenarios mirroring the seeded attack library (`eval_cases/cases.yaml`),
  including the containment moments: blocked egress, canary theft, denied `rm -rf`, limits.
- Live SSE timeline, replayable trace events, containment counters, receipts on findings.
- Demo endpoint (`POST /v1/demo/runs`) with no login; owner-filtered API for real runs.
- Deterministic rule-table verdict; the LLM never decides the verdict.

## Integrate with your team

Every push can get a real Airlock review — verdict, network-anomaly findings and receipts —
via the API:

```bash
# 1. An admin creates a scoped key (Dashboard → Automate, or the API):
curl -X POST $HOST/v1/admin/keys -H "X-API-Key: $ADMIN" \
     -H "Content-Type: application/json" -d '{"owner_id": "team-alpha"}'
# → {"key": "ak_xxxxxxxx.<secret>", ...}   shown once; only the hash is stored

# 2. The team (or CI) submits a PR:
curl -X POST $HOST/v1/runs -H "X-API-Key: ak_xxxxxxxx.<secret>" \
     -H "Content-Type: application/json" \
     -d '{"pr_url": "https://github.com/octo/repo/pull/7"}'
# → poll GET /v1/runs/{id} until completed; verdict + containment counters + receipts
```

For auto-run on every push, add the workflow from [`deploy/examples/`](deploy/examples/README.md)
to the consuming repo — team keys are owner-scoped and owner-isolated, a leaked key sees
nothing but its own runs, and revocation is instant from the Dashboard.

## Not yet (build week, Nov 3–8)

- Real Docker + gVisor backend on the Vultr VM (T11/T12 — `app/sandbox/docker_backend.py` is
  written but validated only on the VM).
- `VultrLLM` end-to-end against the live model catalog (T07 — pick models from
  `GET /v1/models`; never hardcode: the catalog rotates).
- SQL storage, session JWTs, admin/kill-switch endpoints (T08/T09/T24), frontend (T21–T24).

## Public demo site (GitHub Pages)

A static build of `web/` that serves recorded runs with no backend — the same pattern as
blind-run's Pages site. The snapshot (`web/demo/airlock-snapshot.json`) is regenerated
from the real store with `python scripts/export_demo_snapshot.py`; `.github/workflows/pages.yml`
builds and deploys it on push. Setup steps and build notes: [`deploy/GO-LIVE.md` §7](deploy/GO-LIVE.md).

## Layout

```
app/
  agents/       orchestrator (code-owned flow) + planner/fixer/test-writer/analyst/reporter
  api/          routes + auth deps
  core/         settings, errors, trace bus
  guardrails/   policy file, input (URL/injection), output (redaction/command policy)
  preflight/    OSV MAL- + package age + static risk scan
  scoring/      verdict rule table + routing
  sandbox/      base + dummy + docker(runsc) + vultr_vm stub
  sources/      dummy scenarios + GitHub PR fetch
  store/        in-memory repository (owner-filtered)
  workers/      in-process queue
  eval/         benchmark runner
policies/       policy_v1.yaml (versioned; stamped on every run)
eval_cases/     17 seeded cases with expected verdicts
```

Plan of record: `../Airlock Engineering Workbook.md` · verification:
`../Research Verification — Oct 27 2026.md` · build log: `../BUILD-LOG.md`.
