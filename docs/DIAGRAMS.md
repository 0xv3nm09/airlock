# Airlock diagrams

Zones, flows and sequences for the deployed system, drawn from the code in this repository
(`app/`, `web/`, `deploy/`). GitHub renders every diagram below.

1. [Trust zones](#1-trust-zones) — what can talk to what
2. [Review pipeline](#2-review-pipeline) — one PR from URL to verdict
3. [Verdict rule table](#3-verdict-rule-table) — how evidence becomes a label
4. [Sandbox network phases](#4-sandbox-network-phases) — egress only while installing
5. [Sequence: a live run from the browser](#5-sequence-a-live-run-from-the-browser)
6. [Sequence: CI review with a team key](#6-sequence-ci-review-with-a-team-key)
7. [Run lifecycle](#7-run-lifecycle)

---

## 1. Trust zones

Everything runs on one Vultr VM except the external services. PR code only ever executes
in the **untrusted zone**; the control plane never runs it, and the sandboxes hold no real
credentials.

```mermaid
flowchart LR
  subgraph Z0["Zone 0 · Internet (untrusted)"]
    U["Browser / judge"]
    CI["CI job<br/>(team API key)"]
  end

  subgraph VM["Vultr Cloud Compute VM · vc2-4c-8gb"]
    subgraph Z1["Zone 1 · Edge"]
      CADDY["Caddy :80<br/>reverse proxy, SSE flush"]
    end

    subgraph Z2["Zone 2 · Control plane (trusted, our code only)"]
      WEB["Next.js web<br/>dashboard · run view · trace"]
      API["FastAPI API<br/>auth · rate limits · SSE"]
      ORCH["Orchestrator + workers<br/>code-owned pipeline"]
      RULES["Rule table<br/>(decides the verdict)"]
      STORE[("SQLite store<br/>runs · traces · hashed keys")]
      DOCKER["Docker daemon<br/>(via socket)"]
    end

    subgraph Z3["Zone 3 · Sandboxes (untrusted PR code)"]
      SB_BASE["gVisor sandbox · base branch"]
      SB_PR["gVisor sandbox · PR head"]
    end

    subgraph Z4["Zone 4 · Egress control"]
      SQUID["squid proxy<br/>allow: pypi.org,<br/>files.pythonhosted.org,<br/>registry.npmjs.org"]
    end
  end

  subgraph Z5["Zone 5 · External services"]
    VSI["Vultr Serverless Inference<br/>api.vultrinference.com/v1"]
    GH["GitHub API<br/>PR metadata + tarballs"]
    OSV["OSV.dev<br/>known-malware advisories"]
    REG["PyPI / npm registries"]
  end

  U -->|HTTP| CADDY
  CI -->|"POST /v1/runs<br/>X-API-Key"| CADDY
  CADDY --> WEB
  CADDY -->|"/v1/*"| API
  WEB -->|"/api rewrite"| API
  API --> STORE
  API --> ORCH
  ORCH --> STORE
  ORCH --> RULES
  ORCH -->|agent calls| VSI
  ORCH -->|read-only token| GH
  ORCH --> OSV
  ORCH --> DOCKER
  DOCKER -->|create · exec · destroy| SB_BASE
  DOCKER -->|create · exec · destroy| SB_PR
  SB_BASE -.->|install phase only| SQUID
  SB_PR -.->|install phase only| SQUID
  SQUID -->|allow-listed hosts| REG

  classDef untrusted fill:#3b0d14,stroke:#f87171,color:#fde2e2
  classDef trusted fill:#0f2a1c,stroke:#4ade80,color:#dcfce7
  classDef edge fill:#16223a,stroke:#93c5fd,color:#e6edf6
  classDef ext fill:#1f1a33,stroke:#a5b4fc,color:#e6edf6
  class SB_BASE,SB_PR untrusted
  class WEB,API,ORCH,RULES,STORE,DOCKER trusted
  class CADDY,SQUID edge
  class VSI,GH,OSV,REG ext
```

**Boundary rules**

| From → to | Allowed? | Enforced by |
| --- | --- | --- |
| Internet → control plane | Only through Caddy; API and web bind to `127.0.0.1` | `deploy/docker-compose.yml`, `deploy/Caddyfile` |
| Sandbox → internet | Never directly — the egress network is `internal: true` | `airlock-egress` network |
| Sandbox → registries | Install phase only, through squid's allow-list | `deploy/squid.conf`, `use_network()` |
| Sandbox → anything during tests | No network at all (detached before tests) | `app/sandbox/docker_backend.py` |
| Sandbox → host / app | No: gVisor, read-only rootfs, caps dropped, `no-new-privileges` | `DockerSandbox.create()` |
| Real secrets → sandbox | Never. Only randomized canary keys, fresh per run | `make_canaries()` in `app/sandbox/base.py` |
| LLM → verdict | Never. The model advises; the rule table decides | `app/scoring/verdict.py` |

---

## 2. Review pipeline

Cheap checks first; a sandbox is only created when the PR survives pre-flight. Every box
emits trace events (spans, logs, findings, containment, verdict).

```mermaid
flowchart TD
  A["PR URL<br/>(sample button · benchmark case · team key)"] --> B["Input guardrail<br/>strict GitHub PR URL · rate limit"]
  B --> C["Fetch PR<br/>title · body · diff · added deps"]
  C --> D["Pre-flight<br/>prompt-injection screen · static risk scan<br/>OSV known-malware · package age"]
  D -->|known-malicious dependency| STOP["Stop: no sandbox created<br/>finding: known_malicious_dependency"]
  D -->|continue| E["Planner agent (Vultr Serverless Inference)<br/>install + test command from the allow-list<br/>fixed before any untrusted output is read"]
  E --> F["Create twin sandboxes<br/>base branch ∥ PR head<br/>gVisor · read-only root · tmpfs workspace<br/>random canary keys planted"]
  F --> G["Materialize repo tarballs into /workspace"]
  G --> H["Install (egress via squid, registries only)<br/>fixer agent self-heals failed commands"]
  H -->|install failed| INC["tests skipped<br/>→ cannot read as safe"]
  H -->|installed| I["Detach network<br/>run tests on base and PR"]
  I -->|base suite fails| INC
  I -->|baseline OK| J["Test-writer agent<br/>one generated test, kept only if it runs on base"]
  J --> K["Behaviour scan (PR sandbox)<br/>egress attempts · canary hits · denied writes · limits<br/>minus anything the base also did"]
  INC --> K
  STOP --> L
  K --> P["Destroy both sandboxes<br/>(finally — on every path, including failures)"]
  P --> L["Rule table → verdict + route"]
  L --> M["Security analyst agent<br/>explains intent, cannot change the verdict"]
  M --> N["Reporter agent<br/>summary, every claim cited to a finding"]
  N --> O["Persist run + trace · stream final events<br/>(the record outlives the sandboxes)"]
```

---

## 3. Verdict rule table

First match wins. The confidence comes from the evidence behind the matching findings,
never from the model.

```mermaid
flowchart TD
  S(["Findings + tests_ran"]) --> Q1{"Any DANGER finding?<br/>known-malicious dep · secret access (canary)<br/>network attempt · write outside repo · prompt injection"}
  Q1 -->|yes| SUS["SUSPICIOUS<br/>→ always a human reviewer"]
  Q1 -->|no| Q2{"Any proven BREAKING finding?<br/>test regression · generated test fails on PR only<br/>resource abuse (time / memory / pids)"}
  Q2 -->|yes| NC["NEEDS CHANGES<br/>→ human if confidence below 0.80"]
  Q2 -->|no| Q3{"Did tests run on a<br/>working baseline?"}
  Q3 -->|no| INC["INCONCLUSIVE (0.30)<br/>→ human — never a guessed 'safe'"]
  Q3 -->|yes| SAFE["SAFE TO MERGE (0.82, capped)<br/>→ auto"]

  classDef red fill:#3b0d14,stroke:#f87171,color:#fde2e2
  classDef amber fill:#2a1f05,stroke:#fbbf24,color:#fef3c7
  classDef blue fill:#0f1d33,stroke:#60a5fa,color:#dbeafe
  classDef green fill:#0f2a1c,stroke:#4ade80,color:#dcfce7
  class SUS red
  class NC amber
  class INC blue
  class SAFE green
```

---

## 4. Sandbox network phases

A sandbox only has a route out while dependencies install, and only to the package
registries.

```mermaid
stateDiagram-v2
  direction LR
  [*] --> Created: docker run on airlock-egress<br/>(internal network, proxy pinned by IP)
  Created --> Materialized: repo tarball streamed into /workspace
  Materialized --> Installing: pip / npm via squid<br/>registries allowed, everything else denied + logged
  Installing --> Offline: network detached
  Offline --> Testing: tests + generated test<br/>no network at all
  Testing --> Observed: behaviour scan<br/>(canaries · denied writes · limits · egress errors)
  Observed --> Destroyed: container removed (force, volumes)
  Installing --> Destroyed: failure / cancel / timeout
  Testing --> Destroyed: failure / cancel / timeout
  Destroyed --> [*]
```

---

## 5. Sequence: a live run from the browser

A sample button on the live site, end to end. The browser watches the run through
Server-Sent Events; the same events form the replayable trace.

```mermaid
sequenceDiagram
  autonumber
  actor User as Browser
  participant Web as Next.js web
  participant API as FastAPI
  participant Q as Queue / worker
  participant O as Orchestrator
  participant GH as GitHub
  participant LLM as Vultr Serverless Inference
  participant D as Docker + gVisor
  participant SP as squid proxy

  User->>Web: click "Catch the malicious PR live"
  Web->>API: POST /v1/demo/runs {scenario}
  API->>API: per-IP rate limit
  API->>Q: enqueue run (status: queued)
  API-->>Web: 202 {id}
  Web->>API: GET /v1/runs/{id}/events (SSE)
  Q->>O: execute_run(id)
  O->>GH: PR metadata, files, deps
  O->>O: pre-flight (injection · static risk · OSV · package age)
  O->>LLM: planner (structured JSON)
  LLM-->>O: install + test commands, targets
  O->>D: create base + PR sandboxes (random canaries)
  O->>GH: tarballs (base, refs/pull/N/head)
  O->>D: stream tarballs into /workspace
  O->>D: exec install (both sandboxes)
  D->>SP: pip / npm traffic
  SP-->>D: registries allowed · others 403 + logged
  O->>D: detach network · exec tests (base ∥ PR)
  O->>LLM: test-writer → generated test
  O->>D: run generated test on base and PR
  O->>D: behaviour scan (base report subtracted from PR)
  O->>D: destroy both sandboxes (finally, on every path)
  O->>O: rule table → verdict + route
  O->>LLM: analyst + reporter (cite-checked)
  loop every step
    O-->>API: trace event (span · log · finding · containment)
    API-->>User: SSE event (+ keep-alive during long steps)
  end
  API-->>User: status: completed → stream closes
  User->>API: GET /v1/runs/{id} · /trace (receipts, full record)
```

---

## 6. Sequence: CI review with a team key

How a team wires Airlock into CI so every push gets the same review.

```mermaid
sequenceDiagram
  autonumber
  actor Admin
  participant Dash as Dashboard → Automate
  participant API as Airlock API
  participant CI as CI workflow (GitHub Actions)
  participant P as Airlock pipeline

  Admin->>Dash: create key for "team-alpha"
  Dash->>API: POST /v1/admin/keys (admin)
  API-->>Dash: ak_xxxxxxxx.secret (shown once, only the SHA-256 hash is stored)
  Admin->>CI: save as secret AIRLOCK_API_KEY
  Note over CI: on every push / pull_request
  CI->>API: POST /v1/runs {pr_url} · X-API-Key
  API->>API: verify hash · scope runs:write · per-owner rate limit
  API->>P: enqueue run (owner = team-alpha)
  API-->>CI: 202 {id}
  loop until completed
    CI->>API: GET /v1/runs/{id}
    API-->>CI: status · verdict · counters · findings
  end
  alt suspicious, or a review route
    CI-->>CI: e.g. fail the check, link the receipts
  else safe to merge
    CI-->>CI: pass
  end
  Admin->>API: revoke key (instant) if leaked
```

---

## 7. Run lifecycle

```mermaid
stateDiagram-v2
  [*] --> queued: POST /v1/runs · /v1/demo/runs · /v1/benchmark/run/{case}
  queued --> cancelled: cancel before start
  queued --> running: worker picks it up
  running --> completed: verdict reached
  running --> failed: unrecoverable error (sandboxes still destroyed)
  running --> cancelled: cancel at a checkpoint
  completed --> decided: human approves / rejects<br/>(runs:approve, suspicious queue)
  completed --> [*]
  decided --> [*]
  failed --> [*]
  cancelled --> [*]
```
