# Feedback & Issues — build-week retrospective

This is the honest record of what went wrong while building Airlock on Vultr (Nov 3–8,
2026), how each issue was found and fixed, and what worked well enough to keep. It exists
for three readers: the platform teams (Vultr, Next.js, GitHub) who can use the friction
report, future builders deploying the same stack, and judges who want to see how the
project handles failure. Every issue below shipped a fix that is in the repo.

**The scoreboard behind this document:** 19-case live benchmark — **18/19 expected
verdicts**, 0 false safe-to-merge, 0 containment escapes across every sandbox created
(36+ across all sweeps), ~159k tokens of real model spend. The one miss is documented,
not hidden ([results](BENCHMARK-RESULTS.md#known-gaps--documented-not-hidden)).

---

## Part 1 — Issues faced and how they were resolved

### Vultr platform

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 1 | New account could not deploy anything: *"Please verify your account e-mail before deploying new servers"* — and the verification mail never arrived (tried resend, quarantine, safe-senders) | Verification loop unusable when the provider swallows the mail; the email-change confirmation also goes to the same dead inbox | Switched to another Vultr account with verified e-mail; the original stayed gated. **Feedback for Vultr:** offer manual verification or a non-email fallback (support-verified) sooner — this consumed half a build day |
| 2 | `ssh_key_id` at instance create did not inject the key (offered by ssh, rejected by the server); `reinstall` with `ssh_key_id` also silently failed | Injection unreliable; the API's `reinstall` body only accepts `hostname`/`backups` (verified against the official generated SDK) | Set **`user_data` (cloud-config) at create time** writing the pubkey to `authorized_keys` — native create field, deterministic. Baked into `scripts/vultr_deploy.sh` |
| 3 | Serverless Inference is **absent from the OpenAPI spec** — no docs for subscription/API-key creation; `/v2/firewall-group-update` likewise | Spec lags the product | Discovered empirically: `POST /v2/inference` → id → `POST /v2/inference/{id}/api-keys` (the create response carries the key directly). **Feedback for Vultr:** add Inference to the spec and the generated SDK |
| 4 | Firewall rule creation silently failed — our script piped responses to `/dev/null` and the body used `source`, but the schema **requires** `subnet` | Unvalidated script + field-name mismatch | Caught by introspecting the official [`vultr-python-client`](https://github.com/vultr/vultr-python-client); rules fixed to `{"ip_type","protocol","port","subnet","subnet_size"}` and failures now print loudly |
| 5 | Vultr API IP allowlist began rejecting the operator's IP mid-build (401 on every call) | Account-level API access control + a changing public IP | Upload the key to the VM and operate from there; **feedback:** allowlist management is portal-only — an API-scoped exception for automation would help |

### Model selection

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 6 | Planned models failed live: GLM variants returned **empty content** in JSON mode; `qwen3.8-27b` produced empty code output | Catalog models differ wildly in structured-output behaviour; names do not predict it | A live **bake-off** (strict-JSON prompt + code-compilation check, latency measured) picked `minimax-m3.1-flash` for every agent role. **Lesson:** never pick a model by name — the catalog rotates; test before you commit |

### Docker + gVisor (the deepest class)

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 7 | `put_archive`/`docker cp` rejected outright on `--read-only` containers — the daemon never considers tmpfs mounts | Docker blocks all archive writes to read-only rootfs | Stream the repo tarball through an **exec's stdin** into `tar -x`. Three sub-bugs surfaced: `exec_create` needs `stdin=True` or the write lands nowhere; docker-py returns a read-mode `SocketIO` (write via `._sock.sendall` + `SHUT_WR`); `exec_inspect` reports `ExitCode: None` while running (poll before proceeding) |
| 8 | Attaching the egress network to a running `none`-mode container fails: *"cannot be connected to multiple networks with one of the networks in private (none) mode"* | Docker forbids live-attach onto a none-mode container | Join the egress network **at create** (the squid proxy still enforces registries-only) and disconnect entirely after install — same end state, no live-attach |
| 9 | Tests reported *"No module named pytest"* on honest runs | Inside gVisor, a venv's python can resolve with the system prefix; a fixer-proposed plain `python -m venv` rewrites `pyvenv.cfg` and drops `--system-site-packages`, hiding the preinstalled toolchain | The orchestrator re-runs the **fixed** venv step (idempotent) after every successful install |
| 10 | pip's isolated build env intermittently fails under gVisor (`BackendUnavailable`, build-hook crashes) | gVisor + build-isolation interaction; LLM-fixer retries drew failures on some attempts | Self-heal absorbs most; persistent failures route to `inconclusive → human` — the run never reads as a false "safe" |

### Next.js / React (the web app)

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 11 | VM dashboard read **"backend offline"** while every API path answered | Next **bakes `rewrites()` destinations into the build manifest** — the web image was built without `AIRLOCK_API_URL`, so `/api/*` hit the baked fallback `127.0.0.1:8000` | `ENV AIRLOCK_API_URL` before `npm run build` in the Dockerfile. **Lesson:** test the full browser path (`/api/*` through the app server), not only the API routes |
| 12 | `IntersectionObserver` callbacks never fire in the ZCode in-app webview — dashboard counters stuck at 0 even for always-visible elements | Webview-specific IO silence | CountUp checks `getBoundingClientRect` first (animate immediately when on screen) with a 2.5 s settle fallback |
| 13 | Demo buttons stuck on "Starting…" while the run was already live | The starting POST through the `/api` proxy could lag or die without surfacing; the client router then never navigated | 30 s `AbortSignal.timeout` on every JSON request (hung proxy → visible error, button resets) + full `window.location.assign` navigation to the run screen. See [the three warnings](#part-3--the-three-eslint-warnings-kept-on-purpose) |
| 14 | The runs table said "25 of 25" next to a headline of 71 runs | The recent-feed endpoint is capped at 25 by design | Counter now reads "X shown · Y stored · Z lifetime"; numbers use locale formatting |

### GitHub

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 15 | Anonymous API limit (60/h) exhausted mid-sweep — runs failed with *"PR not found or not public"* | Unauthenticated fetches | `AIRLOCK_GITHUB_TOKEN` on the VM (5,000/h) |
| 16 | Force-pushing the **base** branch of open PRs made GitHub close all 19 demo PRs and **permanently block reopening** (REST 422 "force-pushed or recreated"; GraphQL refuses too) | Base-branch force-push under open PRs is an unrecoverable state | Recovered **without deletion**: fresh PRs opened from the same head branches + case URLs renumbered. **Lesson:** never force-push a base branch that PRs sit on; payload fixes go as normal commits to the head branch |
| 17 | Burst API writes produced intermittent empty/404 responses (gh and curl disagreeing) | GitHub-side secondary-limit flakiness | Retries with backoff everywhere; collectors persist progress per case so sweeps resume |

### Data & metrics

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 18 | Dashboard showed **45% inconclusive** and the same case flipping verdicts between runs | Runs from **five code epochs** (broken-DNS installs, silent probes, pre-OSV-parser, venv-clobber era) mixed in one store — the inconsistencies were code evolution, not nondeterminism | Store reset (old store backed up on the VM), all 19 cases rerun once on current code: **18/19**, stable across reruns |
| 19 | `rm-rf-test` reports `safe_to_merge` although the sandbox denied the attack | The denial text dies inside pytest's capture before reaching the behaviour scan (compounded by issue 9) | Documented as the benchmark's one miss with root cause ([known gaps](BENCHMARK-RESULTS.md#known-gaps--documented-not-hidden)); the fix (per-run proxy attribution) is scheduled — we ship the miss instead of quietly editing the expectation |

---

## Part 2 — What was good and worth keeping

- **Vultr Serverless Inference** — OpenAI-compatible, fast (planner calls 1.3–3.6 s), and the
  live `GET /v1/models` catalog made model rotation a config change, not a rewrite.
- **The official generated SDK as ground truth** — introspecting [`vultr-python-client`](https://github.com/vultr/vultr-python-client) caught two script bugs before they cost a deploy.
- **gVisor (`runsc`) held on every path** — zero escapes, zero host writes across every
  sandbox ever created, including the fork-bomb, memory-bomb and rm-rf attacks.
- **Twin-sandbox differential execution** — baseline behaviour is subtracted from PR
  findings, so a repo that phones home on main doesn't frame its own PRs (Nov 7 fix).
- **OSV pre-flight** — known-malicious dependencies stopped in **12.1 s** before any sandbox
  exists: the cheapest containment in the product.
- **SQLite write-through persistence** — every kill, restart and redeploy survived; receipts
  outlived the sandboxes that produced them.
- **Dummy mode** — 98 tests, CI and the whole benchmark run offline at zero credit cost,
  with the mode stated honestly everywhere it is shown.
- **The deterministic rule table** — the same observed facts always produce the same
  verdict; the LLM explains and is cite-checked, never decides.
- **The never-empty public demo** — a committed snapshot of real runs serves the Pages
  site, so the showcase can't go dark when the VM sleeps.

---

## Part 3 — The three ESLint warnings (kept on purpose)

`npm run lint` reports three warnings, all
[`@next/next/no-location-assign-relative-destination`](https://nextjs.org/docs/messages/no-location-assign-relative-destination)
— in `app/console/page.tsx` (the Clean/Buggy/Malicious buttons) and `app/benchmark/page.tsx`
(the "Run live →" buttons):

```ts
window.location.assign(`/runs/${id}`);   // instead of router.push(`/runs/${id}`)
```

**Why they are there.** The rule's preferred alternative — `useRouter().push()` in an event
handler — is exactly what failed in the field (issue 13): the starting POST travels through
the `/api` proxy, and when that connection lagged or died the promise never resolved
cleanly, the router never navigated, and the button sat on "Starting…" next to a feed that
already showed the run. A full browser navigation is unconditional: once the server returns
the run id, the run screen opens. Paired with the 30 s `AbortSignal.timeout` every JSON
request carries, a button can now do exactly two things — navigate, or show an error and
reset. A stuck state is impossible.

**Why not silence it.** The warning is correct as a general default; this is a deliberate,
documented exception with a user-visible failure that motivated it. Deleting the lines to
make lint output clean would reintroduce a bug that a real user reported. Reviewed and kept.

---

## Part 4 — External review findings → fixes (Nov 7)

A post-build review produced four findings; all were accepted and shipped (commit
`47b7769`), verified on the live deployment:

1. **"Findings attributed to the change" was overstated** — the base sandbox's signals were
   ignored, not subtracted. Fixed: the baseline report now suppresses PR-side signals it
   matches; suppressed signals are logged in the trace as *baseline behaviour, not
   attributed*.
2. **Owner-run timelines stalled on "queued"** — the session cookie carried `Secure` in
   prod, so plain-HTTP browsers dropped it and `EventSource` (which cannot send headers)
   went unauthenticated. Fixed: the flag follows the actual request scheme.
3. **Blocked calls that print nothing were invisible** — the stderr host-pattern missed
   proxy `403` responses (and had a latent whitespace bug). Widened (404s deliberately
   excluded — an uninstallable package is not an attack); the remaining limitation is
   stated on the About page.
4. **The live stream stalled after ~30 s of quiet** — the Next rewrite times idle streams
   out while installs run 33–172 s. Fixed: a 15 s SSE comment heartbeat keeps every proxy
   in the chain warm.

---

*Everything referenced here is committed: the fixes in the git history, the numbers in
[`docs/BENCHMARK-RESULTS.md`](BENCHMARK-RESULTS.md), the raw bundle in
[`eval_results/live-benchmark.json`](../eval_results/live-benchmark.json).*
