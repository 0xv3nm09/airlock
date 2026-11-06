# Submission copy — lablab.ai form fields

Paste-ready text for the submission page. Facts are the clean-slate live sweep
(Nov 5, 18/19, 159,067 tokens) — do not inflate.

## Title

**Airlock — Run the PR before you trust it**

## Short description (≤ 200 chars)

> Airlock executes a stranger's pull request inside a gVisor sandbox on Vultr, watches what
> it actually does, and returns a deterministic verdict with receipts — 18/19 on the
> 19-attack live benchmark.

## Long description

Green tests don't tell you a change stopped phoning home. Code review reads the diff —
but the diff is not what runs. Airlock runs the pull request.

**How it works.** Every review runs the same fixed pipeline: injection screen → pre-flight
(OSV known-malware + package age) → static risk scan → a plan fixed *before* untrusted
content is read → **twin gVisor sandboxes** (base vs PR, so behaviour is attributed to the
change, not the repo's baseline) → install behind a registry-only egress proxy → tests
with no network → generated regression tests (kept only if they run on base) → behaviour
scan → **deterministic rule-table verdict** → summary cite-checked against findings →
sandboxes destroyed on every path.

**What the agents do.** Five LLM agents (planner, fixer, test-writer, security analyst,
reporter — `minimax-m3.1-flash` on Vultr Serverless Inference) fill in steps and explain.
They never decide the verdict. Every claim in the summary is cited to a finding, and every
finding carries a receipt: the command, its exit code and output.

**Containment.** gVisor (`runsc`), read-only rootfs, writable tmpfs workspace only, caps
dropped, per-run venv, memory/CPU/PID caps, wall-clock timeouts, registry-only install
egress, **randomized canary secrets planted per run** — code that touches one has proven
exfiltration intent. No real keys ever enter a sandbox, including the customer's.

**Results (live stack, real models):** 18/19 expected verdicts on the seeded 19-attack
library — every exfil, injection and probe caught `suspicious` with receipts; both
unrunnable repos honestly `inconclusive` (never a false "safe to merge"); the one miss is
documented with root cause in the results doc. Known-malicious dependencies are stopped at
pre-flight in 12.1 s before any sandbox exists.

**Stack:** Vultr VM (vc2-4c-8gb) as the control plane · Vultr Serverless Inference for
**all** agent LLM calls · Docker + gVisor sandboxes · FastAPI + Next.js · SQLite
write-through persistence · Caddy + squid registry-only egress.

**Links:** live demo (execute attacks yourself): http://139.84.176.16 ·
repo: https://github.com/0xv3nm09/airlock ·
results: [docs/BENCHMARK-RESULTS.md](https://github.com/0xv3nm09/airlock/blob/main/docs/BENCHMARK-RESULTS.md)

## Technology tags

`vultr` · `serverless-inference` · `gvisor` · `docker` · `fastapi` · `nextjs` ·
`python` · `typescript` · `security` · `sandbox` · `code-review` · `agents` ·
`multi-agent` · `prompt-injection` · `supply-chain`

## Cover image

`docs/screenshots/cover.png` (verdict card over architecture).

## Video

Recorded (4 min, containment moment at 1:20–2:20) — ready to upload with the submission.
