# GO LIVE — Nov 3 kickoff switch-over (dummy → Vultr)

The gift code is shared **at kickoff** (Nov 3, 9:00 PM PKT). Everything below is config —
**no code changes are needed**; the UI reads the backend config live. Budget ~30 minutes
after the Discord Q&A.

## 0. Before touching anything (5 min, during kickoff)

- [ ] Redeem the gift code with a **fresh email** (never tied to Vultr): Billing → Gift
      Code → confirm `$200.00 Remaining Credit`. Set a billing alert.
- [ ] Ask the Discord Q&A: pre-written-code rule (screenshot the answer — it gates `git
      init`), online-prize eligibility.
- [ ] Note the inference key you'll create in step 2 stays **only** in `.env` on the VM.

## 1. Pick the models (5 min)

```bash
curl -s https://api.vultrinference.com/v1/models | python3 -m json.tool | head -50
```

Candidates as of Oct 27: `glm-5.3-flash`, `qwen3.8-27b`, `minimax-m3.1-flash` — the catalog
rotates, so **choose by testing, never by name**. Planner wants long context; coder wants
solid code output. Confirm both are in the list before writing them down.

## 2. Create the Serverless Inference key

Vultr console → Serverless → Inference → Add. Copy the key — it lives only in `.env`.

## 3. Flip `.env` (2 min)

```bash
AIRLOCK_LLM_PROVIDER=vultr
AIRLOCK_VULTR_INFERENCE_API_KEY=<the key>
AIRLOCK_PLANNER_MODEL=<from /v1/models>
AIRLOCK_CODER_MODEL=<from /v1/models>
AIRLOCK_SANDBOX_BACKEND=docker        # VM only — gVisor is Linux-only
AIRLOCK_SANDBOX_RUNTIME=runsc
AIRLOCK_ENV=prod                      # refuses to boot if anything above is still dummy
AIRLOCK_BOOTSTRAP_ADMIN_KEY=<secrets.token_urlsafe(24) value>
AIRLOCK_SESSION_SECRET=<32+ random bytes>
```

## 4. Where (this is the two-stage part)

| Stage | LLM | Sandbox | Where |
| --- | --- | --- | --- |
| Mac (optional, after key exists) | vultr | dummy | gVisor doesn't run on macOS — sandbox stays dummy locally, everything else works |
| Vultr VM (the real thing) | vultr | docker/runsc | deploy per `deploy/README.md` |

## 5. Verify (10 min)

```bash
make check                                # 93 tests, still dummy-independent
uvicorn app.main:app --port 8000 &        # or docker compose up -d
curl -s localhost:8000/readyz             # must read: llm vultr · sandbox docker
```

- [ ] Nav badge reads **"vultr llm · docker sandbox"** (it's dynamic — never hardcoded).
- [ ] Run the malicious demo → verdict arrives with a **real model name** in the trace
      inspector and real token counts.
- [ ] `make bench` on the VM → `eval_results/latest.json` now records
      `mode: vultr/docker`; the benchmark page badge flips to success tone and the footer
      disclaimer switches to "Executed against the live backend…".
- [ ] First real LLM calls: watch for 429s — limits are 120 req/min, 16 concurrent; the
      SDK retries with backoff, so a slow first run is normal.
- [ ] Smoke the whole golden path: home → malicious demo → run view → receipt → trace.

## 6. If anything breaks

- Roll back is one `.env` flip: `AIRLOCK_LLM_PROVIDER=dummy` + restart → the whole product
  returns to the offline demo (this is why dummy mode exists).
- `/readyz` lies about nothing: if it says dummy, it is dummy.
- Keep the dummy `.env` values commented in the file so demo-day fallback is instant.

## 7. Public demo site on GitHub Pages

A static build of the web app that
needs **no backend** — every page reads a committed snapshot of real recorded runs
(`web/demo/airlock-snapshot.json`), so the public site can never go empty or show
"backend offline". Nav shows "public demo · recorded runs"; writes return a clear
pointer to the live deployment.

- [ ] Regenerate the snapshot after new runs worth showing:
      `.venv/bin/python scripts/export_demo_snapshot.py` (from the repo root; API keys are
      never exported). Commit `web/demo/airlock-snapshot.json` with the runs.
- [ ] `.github/workflows/pages.yml` builds the export automatically on every push that
      touches `web/**` (Node 22, `NEXT_PUBLIC_DEMO_MODE=1`, `AIRLOCK_STATIC_BUILD=1`,
      `AIRLOCK_BASE_PATH=/airlock`). **`AIRLOCK_BASE_PATH` must equal the repo name** —
      if the repo isn't named `airlock`, change it in the workflow before the first push.
- [ ] After the repo goes public (same moment as the Nov 3 push — not earlier): repo
      Settings → Pages → Source: **GitHub Actions**. Site lands at
      `https://0xv3nm09.github.io/airlock/`.
- [ ] Local check without pushing:
      `NEXT_PUBLIC_DEMO_MODE=1 AIRLOCK_STATIC_BUILD=1 AIRLOCK_BASE_PATH=/airlock npm run build`
      then serve `web/out` under a `/airlock/` path prefix and open `/airlock/`.
- Build notes: `cacheComponents` (PPR) is disabled automatically in static builds (PPR
  can't export); the run routes prerender one page per recorded run via
  `lib/demo-params.ts`; dashboard numbers render even in webviews with no
  IntersectionObserver support (CountUp settles to the value as a fallback).

