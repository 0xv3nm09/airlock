# Deployment assets (Vultr VM)

Everything the VM needs beyond the app code. Switch-over steps: [`GO-LIVE.md`](GO-LIVE.md).

## Contents

| File | Purpose |
| --- | --- |
| `sandbox_images/Dockerfile.python` | Sandbox image for Python PRs (pytest toolchain preinstalled; deps go into a per-run venv on `/workspace`) |
| `sandbox_images/Dockerfile.node` | Sandbox image for Node PRs (jest preinstalled; deps into `/workspace/node_modules`) |
| `docker-compose.yml` | api + web + postgres + registry-only egress proxy on one VM |
| `squid.conf` | Allow-list: `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org` only; everything else denied and logged |
| `Caddyfile` | Automatic HTTPS; `flush_interval -1` so the SSE timeline streams |

## Quick order (day 1 on the VM)

Also read `GO-LIVE.md` — the Nov 3 switch-over checklist from dummy to real.

```bash
# 1. Docker + gVisor, then the sandbox images
docker build -t airlock-sandbox-python:1 -f deploy/sandbox_images/Dockerfile.python deploy/sandbox_images
docker build -t airlock-sandbox-node:1   -f deploy/sandbox_images/Dockerfile.node   deploy/sandbox_images
# 2. egress network (compose creates it too, but create early for smoke tests)
docker network create airlock-egress --internal || true
# 3. app + proxy
docker compose -f deploy/docker-compose.yml up -d --build
# 4. Caddy with deploy/Caddyfile, DNS at the VM IP (or sslip.io)
```

## Sandbox containment contract (what the backend assumes)

- Root filesystem **read-only**; user **1000**; caps dropped; `no-new-privileges`.
- Started with `network_mode=none`; the `airlock-egress` network is attached **only for
  install** and detached before tests.
- `/workspace` is a 1 GB tmpfs (uid 1000): repo checkout, per-run venv / node_modules, and
  generated tests all live there and die with the container.
- PATH inside the container puts `/workspace/.venv/bin` first (Python).

If `docker network connect` on a running gVisor container ever misbehaves on the VM, the
documented fallback is an install→commit→fresh-none-container variant (requires
a writable rootfs — rejected for containment; only revisit with strong justification).
