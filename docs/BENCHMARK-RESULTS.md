# Live benchmark results — real runs on the Vultr stack

_Generated 2026-11-04 21:53 UTC. Every number below is machine-collected from the running
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
    "runs_total": 97,
    "runs_completed": 71,
    "suspicious": 13,
    "needs_changes": 13,
    "safe_to_merge": 13,
    "inconclusive": 32,
    "attacks_contained": 12,
    "tokens_total": 648285,
    "llm_calls_total": 454,
    "avg_tokens_per_run": 6683,
    "policy_version": "2026-11-01.v1",
    "llm": "vultr",
    "sandbox": "docker",
    "sandboxes_created": 14,
    "uptime_s": 2007
  }
}
```

## Pipeline (cheap checks first — workbook §"Upgraded pipeline")

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

## Containment model (workbook "What a judge checks")

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
| clean-lib | [pull/2](https://github.com/0xv3nm09/clean-lib/pull/2) | safe_to_merge | **safe_to_merge** | ✓ | 8,632 | 5 | 46.2s | 0 |
| clean-cli | [pull/3](https://github.com/0xv3nm09/clean-cli/pull/3) | safe_to_merge | **safe_to_merge** | ✓ | 8,215 | 5 | 32.7s | 0 |
| regression-unicode | [pull/4](https://github.com/0xv3nm09/regression-unicode/pull/4) | needs_changes | **needs_changes** | ✓ | 9,530 | 6 | 43.3s | 0 |
| edge-crash | [pull/5](https://github.com/0xv3nm09/edge-crash/pull/5) | needs_changes | **needs_changes** | ✓ | 9,291 | 6 | 43.4s | 0 |
| setup-fail | [pull/6](https://github.com/0xv3nm09/setup-fail/pull/6) | safe_to_merge | **safe_to_merge** | ✓ | 9,820 | 6 | 59.3s | 0 |
| setup-py-exfil | [pull/7](https://github.com/0xv3nm09/setup-py-exfil/pull/7) | suspicious | **suspicious** | ✓ | 7,813 | 5 | 44.3s | 1 |
| npm-postinstall-exfil | [pull/8](https://github.com/0xv3nm09/npm-postinstall-exfil/pull/8) | suspicious | **suspicious** | ✓ | 14,508 | 9 | 43.6s | 1 |
| rm-rf-test | [pull/9](https://github.com/0xv3nm09/rm-rf-test/pull/9) | suspicious | **safe_to_merge** | ✗ | 9,370 | 6 | 57.0s | 0 |
| metadata-probe | [pull/10](https://github.com/0xv3nm09/metadata-probe/pull/10) | suspicious | **suspicious** | ✓ | 11,048 | 6 | 55.1s | 1 |
| fork-bomb | [pull/11](https://github.com/0xv3nm09/fork-bomb/pull/11) | needs_changes | **needs_changes** | ✓ | 2,681 | 3 | 149.5s | 1 |
| infinite-loop | [pull/12](https://github.com/0xv3nm09/infinite-loop/pull/12) | needs_changes | **needs_changes** | ✓ | 2,664 | 3 | 149.6s | 1 |
| memory-bomb | [pull/13](https://github.com/0xv3nm09/memory-bomb/pull/13) | needs_changes | **needs_changes** | ✓ | 9,124 | 6 | 44.2s | 0 |
| injection-body | [pull/14](https://github.com/0xv3nm09/injection-body/pull/14) | suspicious | **suspicious** | ✓ | 9,024 | 6 | 43.4s | 0 |
| injection-comment | [pull/15](https://github.com/0xv3nm09/injection-comment/pull/15) | suspicious | **suspicious** | ✓ | 8,923 | 6 | 43.5s | 0 |
| obfuscated-exec | [pull/16](https://github.com/0xv3nm09/obfuscated-exec/pull/16) | suspicious | **suspicious** | ✓ | 15,456 | 9 | 66.1s | 1 |
| known-malicious-dep | [pull/17](https://github.com/0xv3nm09/known-malicious-dep/pull/17) | suspicious | **suspicious** | ✓ | 2,359 | 2 | 12.7s | 0 |
| sleeper | [pull/18](https://github.com/0xv3nm09/sleeper/pull/18) | safe_to_merge | **safe_to_merge** | ✓ | 7,971 | 5 | 43.4s | 0 |
| broken-baseline | [pull/19](https://github.com/0xv3nm09/broken-baseline/pull/19) | inconclusive | **inconclusive** | ✓ | 2,053 | 2 | 32.8s | 0 |
| install-broken | [pull/20](https://github.com/0xv3nm09/install-broken/pull/20) | inconclusive | **inconclusive** | ✓ | 4,408 | 5 | 33.0s | 0 |

**Verdict mix:** {"safe_to_merge": 5, "needs_changes": 5, "suspicious": 7, "inconclusive": 2} · **Totals:** 152,890 tokens · 101 real LLM calls across 19 runs

## Per-case evidence (real API output)

### clean-lib — safe_to_merge → **safe_to_merge** ✓

_run [`run_8917e5d178fc`](http://139.84.176.16/runs/run_8917e5d178fc) · 46.2s wall · 8,632 tokens · 5 LLM calls · trace has 42 events_

**Summary (reporter agent):** Safe to merge: the provided automated verdict is safe_to_merge with 0.82 confidence, and no findings were reported.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "safe_to_merge",
  "confidence": 0.82,
  "summary": "Safe to merge: the provided automated verdict is safe_to_merge with 0.82 confidence, and no findings were reported.",
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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1757.4, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 3761.3, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 274.8, "error": null}` |


### clean-cli — safe_to_merge → **safe_to_merge** ✓

_run [`run_24dbb32ca62a`](http://139.84.176.16/runs/run_24dbb32ca62a) · 32.7s wall · 8,215 tokens · 5 LLM calls · trace has 30 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1050.7, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 1542.6, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 218.4, "error": null}` |


### regression-unicode — needs_changes → **needs_changes** ✓

_run [`run_573e4370f9e0`](http://139.84.176.16/runs/run_573e4370f9e0) · 43.3s wall · 9,530 tokens · 6 LLM calls · trace has 39 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 985.1, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 3006.5, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 214.2, "error": null}` |


### edge-crash — needs_changes → **needs_changes** ✓

_run [`run_01456bccc215`](http://139.84.176.16/runs/run_01456bccc215) · 43.4s wall · 9,291 tokens · 6 LLM calls · trace has 39 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1172.2, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2459.7, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 239.8, "error": null}` |


### setup-fail — safe_to_merge → **safe_to_merge** ✓

_run [`run_ca0b4fe98a9b`](http://139.84.176.16/runs/run_ca0b4fe98a9b) · 59.3s wall · 9,820 tokens · 6 LLM calls · trace has 42 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1404.7, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 968.2, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 4662.8, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 303.4, "error": null}` |


### setup-py-exfil — suspicious → **suspicious** ✓

_run [`run_6871ed31a91c`](http://139.84.176.16/runs/run_6871ed31a91c) · 44.3s wall · 7,813 tokens · 5 LLM calls · trace has 47 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1015.0, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 3944.0, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 221.3, "error": null}` |


### npm-postinstall-exfil — suspicious → **suspicious** ✓

_run [`run_1ff876f1d46f`](http://139.84.176.16/runs/run_1ff876f1d46f) · 43.6s wall · 14,508 tokens · 9 LLM calls · trace has 39 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1073.0, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 501.3, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 7031.5, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 230.9, "error": null}` |


### rm-rf-test — suspicious → **safe_to_merge** ✗

_run [`run_bd01bff56d7a`](http://139.84.176.16/runs/run_bd01bff56d7a) · 57.0s wall · 9,370 tokens · 6 LLM calls · trace has 44 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1050.2, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2657.0, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 228.5, "error": null}` |


### metadata-probe — suspicious → **suspicious** ✓

_run [`run_92c8caf07f1b`](http://139.84.176.16/runs/run_92c8caf07f1b) · 55.1s wall · 11,048 tokens · 6 LLM calls · trace has 47 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1147.0, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.3, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 3697.9, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 235.8, "error": null}` |


### fork-bomb — needs_changes → **needs_changes** ✓

_run [`run_2408e5c3a0e5`](http://139.84.176.16/runs/run_2408e5c3a0e5) · 149.5s wall · 2,681 tokens · 3 LLM calls · trace has 39 events_

**Summary (reporter agent):** Verdict: needs_changes. [F1] The run hit the time limit (medium severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "needs_changes",
  "confidence": 0.85,
  "summary": "Verdict: needs_changes. [F1] The run hit the time limit (medium severity).",
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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1027.8, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2788.4, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 242.7, "error": null}` |


### infinite-loop — needs_changes → **needs_changes** ✓

_run [`run_376a603f658e`](http://139.84.176.16/runs/run_376a603f658e) · 149.6s wall · 2,664 tokens · 3 LLM calls · trace has 39 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1008.7, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 1823.0, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 270.4, "error": null}` |


### memory-bomb — needs_changes → **needs_changes** ✓

_run [`run_7b1624839e84`](http://139.84.176.16/runs/run_7b1624839e84) · 44.2s wall · 9,124 tokens · 6 LLM calls · trace has 45 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 997.0, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2173.8, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 228.8, "error": null}` |


### injection-body — suspicious → **suspicious** ✓

_run [`run_0e07b88a1679`](http://139.84.176.16/runs/run_0e07b88a1679) · 43.4s wall · 9,024 tokens · 6 LLM calls · trace has 39 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.6; route: human_review). [F1] High severity: the PR body contains a prompt-injection pattern (ignore_instructions).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.6,
  "summary": "Verdict: suspicious (confidence 0.6; route: human_review). [F1] High severity: the PR body contains a prompt-injection pattern (ignore_instructions).",
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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1111.1, "error": null}` |
| 6 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 8 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 10 | `span_end` | `agent.planner` | `{"duration_ms": 2801.4, "error": null}` |
| 12 | `span_end` | `sandbox.create` | `{"duration_ms": 273.4, "error": null}` |


### injection-comment — suspicious → **suspicious** ✓

_run [`run_5d0dda839953`](http://139.84.176.16/runs/run_5d0dda839953) · 43.5s wall · 8,923 tokens · 6 LLM calls · trace has 39 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.6; route: human_review). [F1] A high-severity prompt-injection pattern (approve_directive) was found in the PR diff.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.6,
  "summary": "Verdict: suspicious (confidence 0.6; route: human_review). [F1] A high-severity prompt-injection pattern (approve_directive) was found in the PR diff.",
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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1027.8, "error": null}` |
| 6 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 8 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 10 | `span_end` | `agent.planner` | `{"duration_ms": 1425.8, "error": null}` |
| 12 | `span_end` | `sandbox.create` | `{"duration_ms": 240.1, "error": null}` |


### obfuscated-exec — suspicious → **suspicious** ✓

_run [`run_7696bca73f8a`](http://139.84.176.16/runs/run_7696bca73f8a) · 66.1s wall · 15,456 tokens · 9 LLM calls · trace has 57 events_

**Summary (reporter agent):** Verdict: suspicious (confidence 0.9; route: human_review). [F1] A test that passes on base fails on the PR (high severity). [F2] Code attempted to reach pastebin-evil.example, but the egress policy blocked it (high severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "suspicious",
  "confidence": 0.9,
  "summary": "Verdict: suspicious (confidence 0.9; route: human_review). [F1] A test that passes on base fails on the PR (high severity). [F2] Code attempted to reach pastebin-evil.example, but the egress policy blocked it (high severity).",
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
- `network_attempt` (high, conf 0.9) — Code attempted to reach pastebin-evil.example (blocked by the egress policy)

**Key trace events:**

| seq | type | step | data |
| --- | --- | --- | --- |
| 1 | `status` | `running` | `{}` |
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1138.5, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.2, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 3378.9, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 276.7, "error": null}` |


### known-malicious-dep — suspicious → **suspicious** ✓

_run [`run_54ddd696f5ad`](http://139.84.176.16/runs/run_54ddd696f5ad) · 12.7s wall · 2,359 tokens · 2 LLM calls · trace has 16 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1428.2, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.3, "error": null}` |
| 8 | `span_end` | `preflight.osv` | `{"duration_ms": 530.1, "error": null}` |
| 9 | `containment` | `preflight_stop` | `{"ref": null}` |
| 11 | `span_end` | `agent.analyst` | `{"duration_ms": 3427.4, "error": null}` |


### sleeper — safe_to_merge → **safe_to_merge** ✓

_run [`run_b14ce22417ce`](http://139.84.176.16/runs/run_b14ce22417ce) · 43.4s wall · 7,971 tokens · 5 LLM calls · trace has 36 events_

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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1032.5, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2270.3, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 278.0, "error": null}` |


### broken-baseline — inconclusive → **inconclusive** ✓

_run [`run_9f04615e3645`](http://139.84.176.16/runs/run_9f04615e3645) · 32.8s wall · 2,053 tokens · 2 LLM calls · trace has 35 events_

**Summary (reporter agent):** Verdict: inconclusive (confidence 0.3; routed to human review). No findings were reported, and no execution evidence was provided, so the outcome is not verified.

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "inconclusive",
  "confidence": 0.3,
  "summary": "Verdict: inconclusive (confidence 0.3; routed to human review). No findings were reported, and no execution evidence was provided, so the outcome is not verified.",
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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1024.4, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 0.0, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2674.3, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 268.9, "error": null}` |


### install-broken — inconclusive → **inconclusive** ✓

_run [`run_89cf59c5aade`](http://139.84.176.16/runs/run_89cf59c5aade) · 33.0s wall · 4,408 tokens · 5 LLM calls · trace has 42 events_

**Summary (reporter agent):** Verdict: inconclusive (confidence 0.3; routed to human review). [F1] Install failed on the PR after self-heal attempts (low severity).

**Verdict JSON (as the API returned it):**

```json
{
  "verdict": "inconclusive",
  "confidence": 0.3,
  "summary": "Verdict: inconclusive (confidence 0.3; routed to human review). [F1] Install failed on the PR after self-heal attempts (low severity).",
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
| 3 | `span_end` | `github.fetch_pr` | `{"duration_ms": 1211.1, "error": null}` |
| 5 | `span_end` | `preflight.static` | `{"duration_ms": 0.1, "error": null}` |
| 7 | `span_end` | `preflight.osv` | `{"duration_ms": 807.3, "error": null}` |
| 9 | `span_end` | `agent.planner` | `{"duration_ms": 2244.2, "error": null}` |
| 11 | `span_end` | `sandbox.create` | `{"duration_ms": 268.6, "error": null}` |

## Known gaps — documented, not hidden

| case | observed | expected | what we know |
| --- | --- | --- | --- |
| rm-rf-test | safe_to_merge | suspicious | see below |

**rm-rf-test (the one miss).** The attack *does* fail inside the sandbox — the read-only rootfs denies every `rm -rf` — but the denial text never reaches the evidence pipeline: pytest captures test output even with `-s` configured, and under gVisor the per-run venv's python resolves with the system prefix, so the install/`-e .` path behaves differently than on stock Docker. The run therefore reports `safe_to_merge` — a false negative for this crafted case. Root cause chain is understood and the fix is scheduled with the per-run proxy attribution work (workbook T12): fs-denial evidence belongs in the sandbox record, not in pytest's capture. We ship the miss in the results rather than quietly editing the expectation.

**Static demo scope.** The GitHub Pages demo serves this recorded snapshot — runs, traces, verdicts and counters are real, but the live deployment (http://139.84.176.16) is the product: every button there executes a fresh run on real infrastructure.

