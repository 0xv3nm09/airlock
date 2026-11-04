# Judging map — Vultr Agent Rush, Challenge 01 "Blast Radius Zero"

Entry: **Airlock — run the PR before you trust it** (Pattern A: sandboxed code execution).
This page maps the official judging criteria and deliverables to concrete evidence in this
repository, so a judge can verify every claim in minutes.

## Judging criteria → evidence

| Criterion | What Airlock does | Where to look |
| --- | --- | --- |
| **Application of Technology** | All agent LLM calls (planner, fixer, test-writer, analyst, reporter) go through Vultr Serverless Inference (`api.vultrinference.com/v1`, OpenAI-compatible). Models are picked from the live catalog at runtime — never hardcoded, because the catalog rotates. Structured-output JSON for every agent; a deterministic rule table turns structured findings into the verdict. | [`app/llm/vultr.py`](../app/llm/vultr.py), [`app/llm/factory.py`](../app/llm/factory.py), [`app/scoring/verdict.py`](../app/scoring/verdict.py), [`deploy/GO-LIVE.md`](../deploy/GO-LIVE.md) |
| **Presentation** | Product-style web app (dashboard, run timeline, trace inspector, benchmark page, review queue), a public no-backend demo site on GitHub Pages serving recorded real runs, and this documentation set. | [`web/`](../web/), [Public demo site](../README.md#public-demo-site-github-pages), [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| **Business Value** | Teams merge third-party code (fork PRs, AI-agent PRs, dependency bumps, vendor drops) without someone hand-auditing it. Every push can be reviewed via a scoped team key + one CI step; suspicious verdicts route to a human (maker-checker) with receipts. | [Integrate with your team](../README.md#integrate-with-your-team), [`deploy/examples/`](../deploy/examples/README.md), [`app/api/routes.py`](../app/api/routes.py) |
| **Originality** | The canary model: Airlock plants randomized, format-valid decoy secrets in every sandbox — if code touches them, that is proven exfiltration intent, not a heuristic. Differential execution (base vs PR in twin sandboxes) means findings are attributed to the change, not the repo's baseline behaviour. | [`app/sandbox/`](../app/sandbox/), [`app/guardrails/policy.py`](../app/guardrails/policy.py), the demo run `run_66d068d12064` in the public demo |

## Deliverables → status

| Deliverable (per rules) | Status | Where |
| --- | --- | --- |
| Public GitHub repo with setup + documentation | ✅ ready — repo flips public at submission; setup in [README](../README.md#quickstart) | this repo |
| Backend deployed on a Vultr VM (control layer) | 🔨 build week — `deploy/` has compose, Caddy, squid egress proxy, sandbox images and the step-by-step runbook | [`deploy/`](../deploy/README.md), [`deploy/GO-LIVE.md`](../deploy/GO-LIVE.md) |
| LLM calls via Vultr Serverless Inference | ✅ adapter written + config-gated; the flip is env vars only (`deploy/GO-LIVE.md` §3) | [`app/llm/vultr.py`](../app/llm/vultr.py) |
| Public demo URL, product-style experience | ✅ static demo site (recorded real runs, works with no backend) + live VM URL once deployed | Pages workflow [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) |
| Recorded video with a "containment moment" | 🔨 pending — scripted moment: the `setup-py-exfil` attack PR passes its tests, then the timeline shows the egress block (`evil.example`) and the canary hit, verdict **suspicious → human**, sandboxes destroyed | demo scenario in `app/sources/dummy.py`, demo video TBD |
| Clear architecture + use case explanation | ✅ | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |

## Rules' containment focus areas → implemented mechanisms

| Focus area (per rules) | Airlock implementation |
| --- | --- |
| **Process isolation** | Every review runs in throwaway Docker containers under gVisor (`runsc`), read-only rootfs, writable tmpfs `/workspace` only, per-run venv, network attached only through an egress proxy that allows package registries. Never inside the app process. |
| **Secret hygiene** | No real secrets ever enter a sandbox — including the customer's: Airlock plants **randomized canary keys** per run instead. Any canary touch is logged and cited as evidence. Logs and traces pass an output redaction pass. |
| **Resource limits** | Memory/CPU/PIDS caps per sandbox, wall-clock test timeouts, and a per-run LLM token budget (120k default) enforced before the verdict step. |
| **Lifecycle discipline** | Sandboxes are destroyed on **every** path — success, failure, cancel, crash — with the destruction step itself recorded in the trace. Run records persist (SQLite write-through) after the environment is gone: evidence outlives the blast radius. |

## The 60-second judge path

1. Open the public demo site (Pages URL) → Dashboard shows 22 recorded real runs, verdict mix and containment feed.
2. Open run `run_66d068d12064` (attack PR `setup-py-exfil`): tests passed, network call to `evil.example` **blocked**, planted AWS-shaped canary **touched** → verdict *suspicious, confidence 0.90, routed to a human*, with the full step-by-step trace.
3. Trace inspector: every span, model call and containment event with timestamps — the raw record behind the verdict.
4. This repo: `make check` (ruff + 98 tests) and `make bench` (19-case attack library, expected-vs-got verdicts) run offline in dummy mode.
