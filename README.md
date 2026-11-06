# Airlock

<p align="center">
  <img src="docs/screenshots/demo.gif" alt="Airlock live demo: the dashboard's real numbers and containment feed, a malicious PR caught red-handed (suspicious, 90% confidence, canary finding), and the full trace inspector" width="820">
</p>

**Run the PR before you trust it.** Airlock runs a stranger's pull request inside a throwaway
sandbox on Vultr, watches what it does, and reports only what it proved. Entry for the
Vultr: Agent Rush Hackathon, Challenge 01 "Blast Radius Zero", Pattern A (sandboxed code
execution).

**Live now:** the full stack runs on a Vultr VM (vc2-4c-8gb, Delhi NCR) — all agent LLM calls
via Vultr Serverless Inference (`minimax-m3.1-flash`), PR execution in Docker + gVisor
(`runsc`) sandboxes behind a registry-only egress proxy. Demo buttons on the live site
execute fresh runs on that stack; offline **dummy mode** remains the zero-credit fallback
and what CI tests.

**Docs:** [Live benchmark results](docs/BENCHMARK-RESULTS.md) ·
[Architecture & use case](docs/ARCHITECTURE.md) · [Judging map](docs/JUDGING.md)
(criteria → evidence, deliverable status) · [Deploy & GO-LIVE runbook](deploy/GO-LIVE.md)

## Results — 19-case attack library, executed live (Nov 2026)

**18/19 expected verdicts matched (94.7%)**, machine-collected from the running deployment
by [`scripts/collect_live_results.py`](scripts/collect_live_results.py) — expected verdicts
come from [`eval_cases/cases.yaml`](eval_cases/cases.yaml), observed ones from the runs'
actual API records. 159,067 tokens · 103 real LLM calls across the sweep.

| verdict | cases | what that means |
| --- | --- | --- |
| **suspicious** | 7 | every exfil, injection and probe caught with receipts: blocked egress, canary-key touches, denied writes, OSV malware stop in 12.1 s (no sandbox created) |
| **needs_changes** | 5 | regressions and resource bombs (fork / infinite-loop / memory) proven by execution, killed by sandbox limits |
| **safe_to_merge** | 5 | clean baselines pass honestly; the sleeping payload is a documented blind spot, not a guess |
| **inconclusive** | 2 | unrunnable repos routed to a human — the rule table refuses to guess; **zero false "safe to merge" on any attack** |

The one miss (`rm-rf-test`, containment held but the denial never reached the evidence
pipeline) is documented, not hidden: [known gaps](docs/BENCHMARK-RESULTS.md#known-gaps--documented-not-hidden).

Per-case evidence in [docs/BENCHMARK-RESULTS.md](docs/BENCHMARK-RESULTS.md): expected-vs-got
table with PR links, verdict JSON for every case, containment counters, trace excerpts, the
pipeline and containment diagrams, and the exact stack facts the runs executed on. Raw
machine bundle: [eval_results/live-benchmark.json](eval_results/live-benchmark.json).
Reproduce with `make bench` (offline) or the collector script (live).

## Quickstart

```bash
cd airlock
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # dev defaults: dummy LLM, dummy sandbox, offline
make check                    # ruff + pytest
make dev                      # API on :8000 (prints a dev admin API key)
make bench                    # 19-case seeded benchmark in dummy mode
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

## What works today (verified offline in dummy mode, live on Vultr)

- Full review pipeline: screen → pre-flight (OSV MAL- check, injection scan, static risk) →
  plan → two sandboxes (base vs PR) → install with self-heal → tests → generated tests →
  behaviour scan → deterministic verdict → summary with cite-check → guaranteed cleanup.
- 19 scripted scenarios mirroring the seeded attack library (`eval_cases/cases.yaml`),
  including the containment moments: blocked egress, canary theft, denied `rm -rf`, limits.
- Live SSE timeline, replayable trace events, containment counters, receipts on findings.
- Demo endpoint (`POST /v1/demo/runs`) with no login; owner-filtered API for real runs.
- Deterministic rule-table verdict; the LLM never decides the verdict.
- Run records persist across backend restarts (SQLite write-through: runs, findings,
  traces, API keys) — the trace outlives the sandbox.
- Team API keys: scoped (`runs:read/write/approve/admin`), hashed, revocable, per-owner
  isolated; a leaked key sees nothing but its own runs.

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

## Shipped during build week

- Vultr VM deployment: FastAPI + web + Postgres + squid egress + Caddy behind compose;
  Docker + gVisor (`runsc`) sandboxes validated live (T11/T12).
- `VultrLLM` end-to-end against the live model catalog — models picked by testing
  (`minimax-m3.1-flash` for every agent role), never hardcoded (T07).
- SQLite write-through persistence, team API keys, static Pages demo, 18/19 live benchmark.

## Remaining before submission (Nov 8)

- Repo goes public + Pages enabled (the static demo deploys on the flip — workflow ready).
- Containment-moment video, recorded on the live deployment (checklist in
  [`docs/JUDGING.md`](docs/JUDGING.md)).
- Cloud firewall rule verification needs the account's API IP allowlist updated; host-level
  exposure is already minimal (only sshd :22 and Caddy :80/:443 are reachable).

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
  store/        repository (owner-filtered; SQLite write-through persistence)
  workers/      in-process queue
  eval/         benchmark runner
policies/       policy_v1.yaml (versioned; stamped on every run)
eval_cases/     19 seeded cases with expected verdicts
docs/           architecture + judging map
```

Full architecture and data flow: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Documentation map

| Document | What it covers |
| --- | --- |
| [`docs/BENCHMARK-RESULTS.md`](docs/BENCHMARK-RESULTS.md) | **Live results** — expected-vs-got table, per-case verdict JSON, containment counters, trace excerpts, pipeline + containment diagrams, known gaps. Rendered from `eval_results/live-benchmark.json` by `scripts/render_results_md.py`. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Use case, full data-flow diagram, twin-sandbox rationale, trust boundaries, challenge stack mapping. |
| [`docs/JUDGING.md`](docs/JUDGING.md) | The four judging criteria mapped to evidence, deliverables checklist with status, containment focus areas → mechanisms, the 60-second judge path. |
| [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) | Which models the five agents use, what each may/may not do, evaluation + limitations. |
| [`docs/SUBMISSION.md`](docs/SUBMISSION.md) | Paste-ready lablab.ai form fields: title, short/long description, tags. |
| [`deploy/GO-LIVE.md`](deploy/GO-LIVE.md) | Dummy→Vultr switch-over runbook (env vars, model selection, verification) + GitHub Pages demo setup (§7). |
| [`deploy/README.md`](deploy/README.md) | Compose stack, Caddy, squid egress proxy, sandbox images — how the VM deployment fits together. |
| [`deploy/examples/README.md`](deploy/examples/README.md) | GitHub Actions workflow to review every push to your own repo (team-key integration). |
| [`web/README.md`](web/README.md) | Frontend: pages, demo mode (static Pages build), env vars. |
| [`eval_cases/cases.yaml`](eval_cases/cases.yaml) | The 19-case seeded attack library: URL + expected verdict per case — the benchmark's source of truth. |
| [`eval_results/live-benchmark.json`](eval_results/live-benchmark.json) | Raw machine bundle of the live sweep (runs, verdicts, counters, usage, full traces). |
| [`policies/policy_v1.yaml`](policies/policy_v1.yaml) | Versioned runtime policy — egress allow-list, command policy, limits; stamped on every run. |

Reference repos (same builder, same demo pattern): [blind-run](https://github.com/0xv3nm09/blind-run)
(Nebius × NVIDIA hackathon winner entry — the static-demo pattern Airlock's Pages site follows).
