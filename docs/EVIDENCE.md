# Evidence map — Vultr Agent Rush, Challenge 01 "Blast Radius Zero"

Entry: **Airlock — run the PR before you trust it** (Pattern A: sandboxed code execution).
This page links each challenge criterion and deliverable to the code, docs and recorded runs
behind it.

## Criteria → evidence

| Criterion | What Airlock does | Where to look |
| --- | --- | --- |
| **Application of Technology** | All agent LLM calls (planner, fixer, test-writer, analyst, reporter) go through Vultr Serverless Inference (`api.vultrinference.com/v1`, OpenAI-compatible). Models are picked from the live catalog at runtime — never hardcoded, because the catalog rotates. Structured-output JSON for every agent; a deterministic rule table turns structured findings into the verdict. | [`app/llm/vultr.py`](../app/llm/vultr.py), [`app/llm/factory.py`](../app/llm/factory.py), [`app/scoring/verdict.py`](../app/scoring/verdict.py), [`deploy/GO-LIVE.md`](../deploy/GO-LIVE.md) |
| **Presentation** | Product-style web app (dashboard, run timeline, trace inspector, benchmark page, review queue), a read-only GitHub Pages site serving recorded real runs, and this documentation set. | [`web/`](../web/), [Public demo site](../README.md#public-demo-site-github-pages), [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| **Business Value** | Teams merge third-party code (fork PRs, AI-agent PRs, dependency bumps, vendor drops) without someone hand-auditing it. Every push can be reviewed via a scoped team key + one CI step; suspicious verdicts route to a human (maker-checker) with receipts. | [Integrate with your team](../README.md#integrate-with-your-team), [`deploy/examples/`](../deploy/examples/README.md), [`app/api/routes.py`](../app/api/routes.py) |
| **Originality** | The canary model: Airlock plants randomized, format-valid decoy secrets in every sandbox — if code touches them, that is proven exfiltration intent, not a heuristic. Differential execution (base vs PR in twin sandboxes) means findings are attributed to the change, not the repo's baseline behaviour. | [`app/sandbox/`](../app/sandbox/), [`app/guardrails/policy.py`](../app/guardrails/policy.py), the recorded run `run_66d068d12064` |

## Deliverables

| Deliverable | Status | Where |
| --- | --- | --- |
| Public GitHub repo with setup + documentation | ✅ public; setup in [README](../README.md#quickstart) | this repo |
| Backend deployed on a Vultr VM (control layer) | ✅ **live** — api + web + Postgres + squid egress + Caddy under compose on vc2-4c-8gb (Delhi NCR); `/readyz` reads `vultr llm · docker sandbox` | [`deploy/`](../deploy/README.md), [`deploy/GO-LIVE.md`](../deploy/GO-LIVE.md) |
| LLM calls via Vultr Serverless Inference | ✅ **live** — every agent call goes through `api.vultrinference.com/v1`; model + tokens stamped per span in the trace inspector | [`app/llm/vultr.py`](../app/llm/vultr.py) |
| Public URL, product-style experience | ✅ **live** — http://139.84.176.16 (run buttons execute fresh runs on the real stack); read-only site of recorded runs at https://0xv3nm09.github.io/airlock/ | Pages workflow [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) |
| Recorded video with a "containment moment" | ✅ **recorded** — the `setup-py-exfil` attack: tests pass, then the timeline shows the egress block (`evil.example`), the canary hit and `suspicious → human`, sandboxes destroyed | submitted with the lablab.ai form |
| Clear architecture + use case explanation | ✅ | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |

## Containment focus areas → mechanisms

| Focus area | Airlock implementation |
| --- | --- |
| **Process isolation** | Every review runs in throwaway Docker containers under gVisor (`runsc`), read-only rootfs, writable tmpfs `/workspace` only, per-run venv, network attached only through an egress proxy that allows package registries. Never inside the app process. |
| **Secret hygiene** | No real secrets ever enter a sandbox — including the customer's: Airlock plants **randomized canary keys** per run instead. Any canary touch is logged and cited as evidence. Logs and traces pass an output redaction pass. |
| **Resource limits** | Memory/CPU/PIDS caps per sandbox, wall-clock test timeouts, and a per-run LLM token budget (120k default) enforced before the verdict step. |
| **Lifecycle discipline** | Sandboxes are destroyed on **every** path — success, failure, cancel, crash — with the destruction step itself recorded in the trace. Run records persist (SQLite write-through) after the environment is gone: evidence outlives the blast radius. |

## A 60-second tour

1. Open the live site (or the read-only Pages site) → Dashboard shows 22 recorded real runs, verdict mix and containment feed.
2. Open run `run_66d068d12064` (attack PR `setup-py-exfil`): tests passed, network call to `evil.example` **blocked**, planted AWS-shaped canary **touched** → verdict *suspicious, confidence 0.90, routed to a human*, with the full step-by-step trace.
3. Trace inspector: every span, model call and containment event with timestamps — the raw record behind the verdict.
4. This repo: `make check` (ruff + 98 tests) and `make bench` (19-case attack library, expected-vs-got verdicts) run offline (no credits needed).
