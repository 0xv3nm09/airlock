# Live benchmark results — real runs on the Vultr stack

_Generated 2026-11-07 18:29 UTC. Every number below is machine-collected from the running
deployment by [`scripts/collect_live_results.py`](../scripts/collect_live_results.py)
— expected verdicts come from [`eval_cases/cases.yaml`](../eval_cases/cases.yaml),
observed ones from the runs' actual API records. Nothing is hand-written._

## The stack these runs executed on

```json
{
  "readyz": {
    "status": "ok",
    "llm": "vultr",
    "sandbox": "docker",
    "policy_version": "2026-11-01.v1",
    "queue_depth": 0,
    "kill_switch": false
  },
  "instance": "vultr vc2-4c-8gb (4 vCPU / 8 GB, Delhi NCR)",
  "models": {
    "planner": "minimax-m3.1-flash (Vultr Serverless Inference)",
    "coder/fixer/test-writer": "minimax-m3.1-flash (Vultr Serverless Inference)"
  },
  "sandbox": "Docker + gVisor (runsc), read-only rootfs, per-run venv, registry-only egress",
  "stats_after_sweep": {
    "runs_total": 21,
    "runs_completed": 20,
    "suspicious": 8,
    "needs_changes": 5,
    "safe_to_merge": 5,
    "inconclusive": 2,
    "attacks_contained": 7,
    "tokens_total": 172070,
    "llm_calls_total": 112,
    "avg_tokens_per_run": 8194,
    "policy_version": "2026-11-01.v1",
    "llm": "vultr",
    "sandbox": "docker",
    "sandboxes_created": 38,
    "uptime_s": 216202
  }
}
```

## Pipeline (cheap checks first)

```text
PR URL
  │
  ▼
[1] Screen ─────────── injection scan on PR text (regex) ──► finding
  ▼
[2] Pre-flight ──────── OSV known-malware + package age
  │                     MAL-* hit ⇒ suspicious NOW, no sandbox ever created
  ▼
[3] Static risk ─────── diff rules: install hooks, base64+exec, subprocess+URL
  ▼
[4] Plan ────────────── fixed BEFORE untrusted content is read (planner agent)
  ▼
[5] Detonate ────────── twin sandboxes (base ∥ PR), gVisor, read-only rootfs
  │   install behind the logging egress proxy (registries only)
  │   tests with NO network; base vs PR compared
  ▼
[6] Generated tests ─── kept only if they run on base
  ▼
[7] Behaviour scan ──── egress blocks · canary hits · denied writes · limits
  ▼
[8] Security analyst ─ explains intent from evidence (LLM) — never decides
  ▼
[9] Rule table verdict ► route (auto / human) ► summary (cite-checked)
  │
  ▼
Destroy sandboxes ──── on every path; the trace + SQLite record survive
```

## Containment model

```text
┌─────────────────────────── sandbox (per run, ×2: base + PR) ──────────────────────────┐
│ gVisor (runsc) kernel below the container        — no host access, no privileged ops   │
│ rootfs: READ-ONLY                                — writes only to /workspace tmpfs     │
│ user 1000, caps dropped, no-new-privileges       — even root inside can't escalate     │
│ network: egress via squid proxy ONLY             — registries allow-listed, rest DENIED│
│   (test phase: network dropped entirely)         — tests run dark                      │
│ canary secrets planted per run                   — touching them = proven exfil intent │
│ limits: mem/cpu/pids + wall-clock                — bombs end by kill, not by trust     │
│ lifecycle: destroyed on EVERY path               — recorded as the trace's last span   │
└────────────────────────────────────────────────────────────────────────────────────────┘
        │ no customer keys ever enter            │ nothing survives except the evidence
        ▼                                        ▼
   canaries in, only canaries out        trace events → SQLite → this document
```

## Results — 18/19 expected verdicts matched

| case | PR | expected | got | match | tokens | llm calls | wall | containment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean-lib | [pull/2](https://github.com/0xv3nm09/clean-lib/pull/2) | safe_to_merge | **safe_to_merge** | ✓ | 8,315 | 5 | 46.4s | 0 |
| clean-cli | [pull/3](https://github.com/0xv3nm09/clean-cli/pull/3) | safe_to_merge | **safe_to_merge** | ✓ | 8,371 | 5 | 33.5s | 0 |
| regression-unicode | [pull/4](https://github.com/0xv3nm09/regression-unicode/pull/4) | needs_changes | **needs_changes** | ✓ | 9,597 | 6 | 44.2s | 0 |
| edge-crash | [pull/5](https://github.com/0xv3nm09/edge-crash/pull/5) | needs_changes | **needs_changes** | ✓ | 10,412 | 7 | 44.3s | 0 |
| setup-fail | [pull/6](https://github.com/0xv3nm09/setup-fail/pull/6) | safe_to_merge | **safe_to_merge** | ✓ | 8,171 | 5 | 55.0s | 0 |
| setup-py-exfil | [pull/7](https://github.com/0xv3nm09/setup-py-exfil/pull/7) | suspicious | **suspicious** | ✓ | 8,853 | 6 | 48.3s | 1 |
| npm-postinstall-exfil | [pull/8](https://github.com/0xv3nm09/npm-postinstall-exfil/pull/8) | suspicious | **suspicious** | ✓ | 9,750 | 6 | 33.6s | 1 |
| rm-rf-test | [pull/9](https://github.com/0xv3nm09/rm-rf-test/pull/9) | suspicious | **safe_to_merge** | ✗ | 9,440 | 6 | 55.0s | 0 |
| metadata-probe | [pull/10](https://github.com/0xv3nm09/metadata-probe/pull/10) | suspicious | **suspicious** | ✓ | 10,977 | 6 | 55.2s | 1 |
| fork-bomb | [pull/11](https://github.com/0xv3nm09/fork-bomb/pull/11) | needs_changes | **needs_changes** | ✓ | 9,224 | 6 | 172.6s | 1 |
| infinite-loop | [pull/12](https://github.com/0xv3nm09/infinite-loop/pull/12) | needs_changes | **needs_changes** | ✓ | 10,019 | 6 | 172.5s | 1 |
| memory-bomb | [pull/13](https://github.com/0xv3nm09/memory-bomb/pull/13) | needs_changes | **needs_changes** | ✓ | 9,464 | 6 | 44.2s | 0 |
| injection-body | [pull/14](https://github.com/0xv3nm09/injection-body/pull/14) | suspicious | **suspicious** | ✓ | 8,941 | 6 | 44.1s | 0 |
| injection-comment | [pull/15](https://github.com/0xv3nm09/injection-comment/pull/15) | suspicious | **suspicious** | ✓ | 10,333 | 7 | 44.2s | 0 |
| obfuscated-exec | [pull/16](https://github.com/0xv3nm09/obfuscated-exec/pull/16) | suspicious | **suspicious** | ✓ | 9,141 | 6 | 44.3s | 1 |
| known-malicious-dep | [pull/17](https://github.com/0xv3nm09/known-malicious-dep/pull/17) | suspicious | **suspicious** | ✓ | 2,359 | 2 | 12.1s | 0 |
| sleeper | [pull/18](https://github.com/0xv3nm09/sleeper/pull/18) | safe_to_merge | **safe_to_merge** | ✓ | 8,423 | 5 | 44.2s | 0 |
| broken-baseline | [pull/19](https://github.com/0xv3nm09/broken-baseline/pull/19) | inconclusive | **inconclusive** | ✓ | 2,557 | 2 | 33.5s | 0 |
| install-broken | [pull/20](https://github.com/0xv3nm09/install-broken/pull/20) | inconclusive | **inconclusive** | ✓ | 4,720 | 5 | 33.6s | 0 |

**Verdict mix:** {"safe_to_merge": 5, "needs_changes": 5, "suspicious": 7, "inconclusive": 2} · **Totals:** 159,067 tokens · 103 real LLM calls across 19 runs

## Per-case evidence (real API output)

### clean-lib — safe_to_merge → **safe_to_merge** ✓

_run [`run_056f7933ceaf`](http://139.84.176.16/runs/run_056f7933ceaf) · 46.4s wall · 8,315 tokens · 5 LLM calls · trace has 42 events_

**Summary (reporter agent):** Safe to merge (confidence 0.82, auto route); no findings were reported.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "safe_to_merge",
  "confidence": 0.82,
  "summary": "Safe to merge (confidence 0.82, auto route); no findings were reported.",
  "reasons": [
    "all tests pass on base and PR; no risky behaviour"
  ],
  "cited_findings": []
}
```

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1179.2, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2554.8, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 355.6, "error": null}` |


### clean-cli — safe_to_merge → **safe_to_merge** ✓

_run [`run_21a9d9e23773`](http://139.84.176.16/runs/run_21a9d9e23773) · 33.5s wall · 8,371 tokens · 5 LLM calls · trace has 30 events_

**Summary (reporter agent):** Safe to merge (confidence 0.82, auto route); no findings were reported.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "safe_to_merge",
  "confidence": 0.82,
  "summary": "Safe to merge (confidence 0.82, auto route); no findings were reported.",
  "reasons": [
    "all tests pass on base and PR; no risky behaviour"
  ],
  "cited_findings": []
}
```

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1121.9, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 1905.5, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 254.7, "error": null}` |


### regression-unicode — needs_changes → **needs_changes** ✓

_run [`run_62c9e7c8f015`](http://139.84.176.16/runs/run_62c9e7c8f015) · 44.2s wall · 9,597 tokens · 6 LLM calls · trace has 45 events_

**Summary (reporter agent):** Verdict: needs changes. [F1] A test that passes on base fails on the PR (high severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "needs_changes",
  "confidence": 0.85,
  "summary": "Verdict: needs changes. [F1] A test that passes on base fails on the PR (high severity).",
  "reasons": [
    "test_regression proven (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Findings:**

- `test_regression` (high, conf 0.85) — A test that passes on base fails on the PR

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1127.3, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 3041.0, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 235.1, "error": null}` |


### edge-crash — needs_changes → **needs_changes** ✓

_run [`run_d0fe217ffcf9`](http://139.84.176.16/runs/run_d0fe217ffcf9) · 44.3s wall · 10,412 tokens · 7 LLM calls · trace has 45 events_

**Summary (reporter agent):** Verdict: needs changes. [F1] A test that passes on base fails on the PR (high severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "needs_changes",
  "confidence": 0.85,
  "summary": "Verdict: needs changes. [F1] A test that passes on base fails on the PR (high severity).",
  "reasons": [
    "test_regression proven (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Findings:**

- `test_regression` (high, conf 0.85) — A test that passes on base fails on the PR

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1198.1, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2936.2, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 239.8, "error": null}` |


### setup-fail — safe_to_merge → **safe_to_merge** ✓

_run [`run_41cdcafacac4`](http://139.84.176.16/runs/run_41cdcafacac4) · 55.0s wall · 8,171 tokens · 5 LLM calls · trace has 42 events_

**Summary (reporter agent):** Safe to merge (confidence 0.82, auto route); no findings were reported.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "safe_to_merge",
  "confidence": 0.82,
  "summary": "Safe to merge (confidence 0.82, auto route); no findings were reported.",
  "reasons": [
    "all tests pass on base and PR; no risky behaviour"
  ],
  "cited_findings": []
}
```

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1844.0, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 929.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2489.6, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 266.3, "error": null}` |


### setup-py-exfil — suspicious → **suspicious** ✓

_run [`run_3049b41544ff`](http://139.84.176.16/runs/run_3049b41544ff) · 48.3s wall · 8,853 tokens · 6 LLM calls · trace has 47 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.9; route: human_review). [F1] Install failed on PR after self-heal attempts (low severity). [F2] Code read or leaked planted canary secrets (critical severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.9,
  "summary": "Verdict: suspicious (confidence 0.9; route: human_review). [F1] Install failed on PR after self-heal attempts (low severity). [F2] Code read or leaked planted canary secrets (critical severity).",
  "reasons": [
    "secret_access found (F2)"
  ],
  "cited_findings": [
    "F1",
    "F2"
  ]
}
```

**Containment counters (observed, not asserted):**

```json
{
  "network_blocked": 0,
  "canary_hits": 1,
  "writes_denied": 0,
  "limits_hit": 0
}
```

**Findings:**

- `setup_failure` (low, conf 0.9) — Install failed on pr after self-heal attempts
- `secret_access` (critical, conf 0.9) — Code read or leaked planted canary secrets

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1341.3, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 3616.1, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 240.7, "error": null}` |


### npm-postinstall-exfil — suspicious → **suspicious** ✓

_run [`run_00322f2e7796`](http://139.84.176.16/runs/run_00322f2e7796) · 33.6s wall · 9,750 tokens · 6 LLM calls · trace has 34 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.9; route: human_review). [F1] Critical: Code read or leaked planted canary secrets.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.9,
  "summary": "Verdict: suspicious (confidence 0.9; route: human_review). [F1] Critical: Code read or leaked planted canary secrets.",
  "reasons": [
    "secret_access found (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Containment counters (observed, not asserted):**

```json
{
  "network_blocked": 0,
  "canary_hits": 1,
  "writes_denied": 0,
  "limits_hit": 0
}
```

**Findings:**

- `secret_access` (critical, conf 0.9) — Code read or leaked planted canary secrets

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1313.5, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.3, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 448.9, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2735.4, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 252.2, "error": null}` |


### rm-rf-test — suspicious → **safe_to_merge** ✗

_run [`run_cd84cb8a56dd`](http://139.84.176.16/runs/run_cd84cb8a56dd) · 55.0s wall · 9,440 tokens · 6 LLM calls · trace has 44 events_

**Summary (reporter agent):** Safe to merge (confidence 0.82, auto route); no findings were reported.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "safe_to_merge",
  "confidence": 0.82,
  "summary": "Safe to merge (confidence 0.82, auto route); no findings were reported.",
  "reasons": [
    "all tests pass on base and PR; no risky behaviour"
  ],
  "cited_findings": []
}
```

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1165.2, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2556.6, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 253.6, "error": null}` |


### metadata-probe — suspicious → **suspicious** ✓

_run [`run_84cac2f33d51`](http://139.84.176.16/runs/run_84cac2f33d51) · 55.2s wall · 10,977 tokens · 6 LLM calls · trace has 47 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.9; route: human_review). [F1] A test that passes on base fails on the PR. [F2] Code attempted to reach 169.254.169.254, which was blocked by the egress policy.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.9,
  "summary": "Verdict: suspicious (confidence 0.9; route: human_review). [F1] A test that passes on base fails on the PR. [F2] Code attempted to reach 169.254.169.254, which was blocked by the egress policy.",
  "reasons": [
    "network_attempt found (F2)"
  ],
  "cited_findings": [
    "F1",
    "F2"
  ]
}
```

**Containment counters (observed, not asserted):**

```json
{
  "network_blocked": 1,
  "canary_hits": 0,
  "writes_denied": 0,
  "limits_hit": 0
}
```

**Findings:**

- `test_regression` (high, conf 0.85) — A test that passes on base fails on the PR
- `network_attempt` (critical, conf 0.9) — Code attempted to reach 169.254.169.254 (blocked by the egress policy)

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1968.3, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.3, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 3697.9, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 269.3, "error": null}` |


### fork-bomb — needs_changes → **needs_changes** ✓

_run [`run_162d3d5f3968`](http://139.84.176.16/runs/run_162d3d5f3968) · 172.6s wall · 9,224 tokens · 6 LLM calls · trace has 46 events_

**Summary (reporter agent):** Verdict: needs changes. [F1] The run hit the time limit (medium severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "needs_changes",
  "confidence": 0.85,
  "summary": "Verdict: needs changes. [F1] The run hit the time limit (medium severity).",
  "reasons": [
    "resource_abuse proven (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Containment counters (observed, not asserted):**

```json
{
  "network_blocked": 0,
  "canary_hits": 0,
  "writes_denied": 0,
  "limits_hit": 1
}
```

**Findings:**

- `resource_abuse` (medium, conf 0.85) — Run hit the time limit

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1191.5, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2366.9, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 230.2, "error": null}` |


### infinite-loop — needs_changes → **needs_changes** ✓

_run [`run_febf7d7aec8f`](http://139.84.176.16/runs/run_febf7d7aec8f) · 172.5s wall · 10,019 tokens · 6 LLM calls · trace has 46 events_

**Summary (reporter agent):** Verdict: needs changes. [F1] The run hit the time limit (medium severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "needs_changes",
  "confidence": 0.85,
  "summary": "Verdict: needs changes. [F1] The run hit the time limit (medium severity).",
  "reasons": [
    "resource_abuse proven (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Containment counters (observed, not asserted):**

```json
{
  "network_blocked": 0,
  "canary_hits": 0,
  "writes_denied": 0,
  "limits_hit": 1
}
```

**Findings:**

- `resource_abuse` (medium, conf 0.85) — Run hit the time limit

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1213.3, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 4094.5, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 288.0, "error": null}` |


### memory-bomb — needs_changes → **needs_changes** ✓

_run [`run_3b8309a87683`](http://139.84.176.16/runs/run_3b8309a87683) · 44.2s wall · 9,464 tokens · 6 LLM calls · trace has 45 events_

**Summary (reporter agent):** Verdict: needs changes. [F1] A test that passes on base fails on the PR (high severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "needs_changes",
  "confidence": 0.85,
  "summary": "Verdict: needs changes. [F1] A test that passes on base fails on the PR (high severity).",
  "reasons": [
    "test_regression proven (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Findings:**

- `test_regression` (high, conf 0.85) — A test that passes on base fails on the PR

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1105.9, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2814.7, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 232.7, "error": null}` |


### injection-body — suspicious → **suspicious** ✓

_run [`run_a583009c4f24`](http://139.84.176.16/runs/run_a583009c4f24) · 44.1s wall · 8,941 tokens · 6 LLM calls · trace has 45 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.6; route: human_review). [F1] High-severity prompt-injection pattern (ignore_instructions) was detected in the PR body.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.6,
  "summary": "Verdict: suspicious (confidence 0.6; route: human_review). [F1] High-severity prompt-injection pattern (ignore_instructions) was detected in the PR body.",
  "reasons": [
    "prompt_injection found (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Findings:**

- `prompt_injection` (high, conf 0.6) — Prompt-injection pattern (ignore_instructions) in PR body

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1083.2, "error": null}` |
| 6 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 8 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 10 | `span_end` | `agent.planner` | `{"duration_ms": 1681.6, "error": null}` |
| 12 | `span_end` | `sandbox.create` | `{"duration_ms": 259.2, "error": null}` |


### injection-comment — suspicious → **suspicious** ✓

_run [`run_0fa9d1b4b798`](http://139.84.176.16/runs/run_0fa9d1b4b798) · 44.2s wall · 10,333 tokens · 7 LLM calls · trace has 45 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.6; route: human_review). [F1] A high-severity prompt-injection pattern (approve_directive) was identified in the PR diff.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.6,
  "summary": "Verdict: suspicious (confidence 0.6; route: human_review). [F1] A high-severity prompt-injection pattern (approve_directive) was identified in the PR diff.",
  "reasons": [
    "prompt_injection found (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Findings:**

- `prompt_injection` (high, conf 0.6) — Prompt-injection pattern (approve_directive) in PR diff

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1133.4, "error": null}` |
| 6 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 8 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 10 | `span_end` | `agent.planner` | `{"duration_ms": 3245.0, "error": null}` |
| 12 | `span_end` | `sandbox.create` | `{"duration_ms": 245.5, "error": null}` |


### obfuscated-exec — suspicious → **suspicious** ✓

_run [`run_ef09ebc6cc9e`](http://139.84.176.16/runs/run_ef09ebc6cc9e) · 44.3s wall · 9,141 tokens · 6 LLM calls · trace has 47 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.9; route: human_review). [F1] Install failed on the PR after self-heal attempts. [F2] Code attempted to reach pastebin-evil.example, but the egress policy blocked it.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.9,
  "summary": "Verdict: suspicious (confidence 0.9; route: human_review). [F1] Install failed on the PR after self-heal attempts. [F2] Code attempted to reach pastebin-evil.example, but the egress policy blocked it.",
  "reasons": [
    "network_attempt found (F2)"
  ],
  "cited_findings": [
    "F1",
    "F2"
  ]
}
```

**Containment counters (observed, not asserted):**

```json
{
  "network_blocked": 1,
  "canary_hits": 0,
  "writes_denied": 0,
  "limits_hit": 0
}
```

**Findings:**

- `setup_failure` (low, conf 0.9) — Install failed on pr after self-heal attempts
- `network_attempt` (high, conf 0.9) — Code attempted to reach pastebin-evil.example (blocked by the egress policy)

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1115.9, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 7273.1, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 224.2, "error": null}` |


### known-malicious-dep — suspicious → **suspicious** ✓

_run [`run_0c206c77fc82`](http://139.84.176.16/runs/run_0c206c77fc82) · 12.1s wall · 2,359 tokens · 2 LLM calls · trace has 16 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.95; route: human_review). [F1] Critical: dependency frd-rsa-js@? matches known-malicious advisory MAL-2024-1042.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.95,
  "summary": "Verdict: suspicious (confidence 0.95; route: human_review). [F1] Critical: dependency frd-rsa-js@? matches known-malicious advisory MAL-2024-1042.",
  "reasons": [
    "known_malicious_dependency found (F1)"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Findings:**

- `known_malicious_dependency` (critical, conf 0.95) — Dependency frd-rsa-js@? matches known-malicious advisory MAL-2024-1042

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1163.5, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.3, "error": null}` |
| 8 | `span_end` | `preflight.osv` | `{"duration_ms": 555.0, "error": null}` |
| 9 | `containment` | `preflight_stop` | `{"ref": null}` |
| 11 | `span_end` | `agent.analyst` | `{"duration_ms": 3352.9, "error": null}` |


### sleeper — safe_to_merge → **safe_to_merge** ✓

_run [`run_4edbed8cc35d`](http://139.84.176.16/runs/run_4edbed8cc35d) · 44.2s wall · 8,423 tokens · 5 LLM calls · trace has 42 events_

**Summary (reporter agent):** Verdict: safe to merge (confidence 0.82; route: auto). No findings were reported.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "safe_to_merge",
  "confidence": 0.82,
  "summary": "Verdict: safe to merge (confidence 0.82; route: auto). No findings were reported.",
  "reasons": [
    "all tests pass on base and PR; no risky behaviour"
  ],
  "cited_findings": []
}
```

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1150.6, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2792.7, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 226.9, "error": null}` |


### broken-baseline — inconclusive → **inconclusive** ✓

_run [`run_db16b71dbc85`](http://139.84.176.16/runs/run_db16b71dbc85) · 33.5s wall · 2,557 tokens · 2 LLM calls · trace has 41 events_

**Summary (reporter agent):** Verdict: inconclusive (confidence 0.3), routed to human review. No findings were reported, and execution was not verified.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "inconclusive",
  "confidence": 0.3,
  "summary": "Verdict: inconclusive (confidence 0.3), routed to human review. No findings were reported, and execution was not verified.",
  "reasons": [
    "tests could not be executed"
  ],
  "cited_findings": []
}
```

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1135.4, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2942.5, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 229.9, "error": null}` |


### install-broken — inconclusive → **inconclusive** ✓

_run [`run_96884ea50a4c`](http://139.84.176.16/runs/run_96884ea50a4c) · 33.6s wall · 4,720 tokens · 5 LLM calls · trace has 45 events_

**Summary (reporter agent):** Verdict: inconclusive (confidence 0.3; routed for human review). [F1] Install failed on the PR after self-heal attempts (low severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "inconclusive",
  "confidence": 0.3,
  "summary": "Verdict: inconclusive (confidence 0.3; routed for human review). [F1] Install failed on the PR after self-heal attempts (low severity).",
  "reasons": [
    "tests could not be executed"
  ],
  "cited_findings": [
    "F1"
  ]
}
```

**Findings:**

- `setup_failure` (low, conf 0.9) — Install failed on pr after self-heal attempts

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1119.5, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 906.6, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2520.3, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 234.8, "error": null}` |

## Known gaps — documented, not hidden

| case | observed | expected | what we know |
| --- | --- | --- | --- |
| rm-rf-test | safe_to_merge | suspicious | see below |

**rm-rf-test (the one miss).** The attack *does* fail inside the sandbox — the read-only rootfs denies every `rm -rf` — but the denial text never reaches the evidence pipeline: pytest captures test output even with `-s` configured, and under gVisor the per-run venv's python resolves with the system prefix, so the install/`-e .` path behaves differently than on stock Docker. The run therefore reports `safe_to_merge` — a false negative for this crafted case. Root cause chain is understood and the fix is scheduled with the per-run proxy attribution work: fs-denial evidence belongs in the sandbox record, not in pytest's capture. We ship the miss in the results rather than quietly editing the expectation.

**Static demo scope.** The GitHub Pages demo serves this recorded snapshot — runs, traces, verdicts and counters are real, but the live deployment (http://139.84.176.16) is the product: every button there executes a fresh run on real infrastructure.

