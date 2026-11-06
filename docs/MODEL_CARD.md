# Model Card — Airlock agents

Airlock is not a single model: it is a deterministic review pipeline in which **five small
LLM agents** each do one job, and **the verdict is decided by a rule table over observed
sandbox facts — never by a model.**

## Models used

| Role | Model | Why |
| --- | --- | --- |
| Planner, Fixer, Test-writer, Security analyst, Reporter | `minimax-m3.1-flash` via Vultr Serverless Inference | Selected by live testing on 2026-11-04 against the rotating catalog (candidates `glm-5.3-flash`, `glm-5.3`, `qwen3.8-27b`, `minimax-m3.1-flash`): strict-JSON reliability and code quality; GLM variants returned empty content in JSON mode |

- Inference endpoint: `https://api.vultrinference.com/v1` (OpenAI-compatible), per the
  challenge's required stack. Models are picked from the live `GET /v1/models` catalog at
  configuration time and are **never hardcoded** — the catalog rotates.
- Structured output (JSON schema) for every agent; a malformed reply is retried, then the
  deterministic fallback plan/summary is used (`model=vultr, fallback=False` is visible per
  span in the trace inspector).

## What each agent may and may not do

| Agent | May | May NOT |
| --- | --- | --- |
| Planner | choose install/test commands from the allow-list, rank ≤3 target files | invent steps; network access |
| Fixer | propose ONE corrected install command from the allow-list | anything outside the allow-list (policy-checked) |
| Test-writer | write ONE self-contained regression test | network, writes outside the repo |
| Security analyst | explain intent, cite finding IDs | change the verdict |
| Reporter | write the plain-language summary | add claims not cited to findings (cite-checked) |

## Data & training

- No model is trained or fine-tuned. No repository content is used for training.
- Prompts contain only the PR metadata, the diff, ranked risk targets and sandbox
  evidence; no customer secrets ever enter a prompt (canary decoys stand in for secrets).

## Evaluation

- 19-case seeded attack library with expected verdicts
  ([`eval_cases/cases.yaml`](../eval_cases/cases.yaml)): **18/19 matched on the live Vultr
  stack** ([results](BENCHMARK-RESULTS.md)); the single miss is documented with root cause.
- Deterministic replay: the same observed facts always produce the same verdict.

## Limitations (stated on the product's About page)

- Python and Node only; no private dependencies; malware that sleeps or detects sandboxes
  may pass (the sleeper case is shipped as an honest blind spot).
- A deterministic rule table trades coverage for predictability: unknown attack shapes
  route to a human (`inconclusive`) rather than guessing.
