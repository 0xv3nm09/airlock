#!/usr/bin/env bash
# Staged Vultr deployment for Airlock (build-week runbook, complements deploy/GO-LIVE.md).
# Reads the Vultr API key from ~/.vultr/api-key (created with `umask 177`) — the key is
# never echoed. Stages:
#   infra   create/verify the VM + firewall + Serverless Inference subscription & key
#   server  provision the VM (docker + gVisor + repo + compose up), dummy/staging fallback
#   flip    switch the live stack to vultr LLM + prod env (needs the inference key)
#   status  instance, readyz, public stats
set -uo pipefail

KEY_FILE="$HOME/.vultr/api-key"
INF_KEY_FILE="$HOME/.vultr/inference-key"
SSH_KEY="$HOME/.ssh/airlock_deploy"
REGION="del"                 # Delhi NCR — closest to Lahore
PLAN="vc2-4c-8gb"            # 4 vCPU / 8 GB — the workbook's pick
OS_ID="2284"                 # Ubuntu 24.04 LTS x64
SSH_KEY_ID="5479b6f4-3886-401d-8bb2-175f57f0ea6b"  # airlock-deploy (uploaded to the coo@magnusmage account)
FW_GROUP="airlock-fw"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

api() { curl -s -m 30 -H "Authorization: Bearer $(cat "$KEY_FILE")" -H "Content-Type: application/json" "$@"; }
instance_id() { api "https://api.vultr.com/v2/instances?tag=airlock&per_page=10" | python3 -c "import json,sys;s=json.load(sys.stdin)['instances'];print(s[0]['id'] if s else '')"; }
instance_ip() { api "https://api.vultr.com/v2/instances?tag=airlock&per_page=10" | python3 -c "import json,sys;s=json.load(sys.stdin)['instances'];print(s[0]['main_ip'] if s else '')"; }
ssh_vm() { ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "root@$(instance_ip)" "$@"; }

stage_infra() {
  set -e
  ID="$(instance_id)"
  if [ -z "$ID" ]; then
    echo ">> creating instance ($REGION / $PLAN)…"
    api -X POST "https://api.vultr.com/v2/instances" -d "{\"region\":\"$REGION\",\"plan\":\"$PLAN\",\"os_id\":$OS_ID,\"ssh_key_id\":[\"$SSH_KEY_ID\"],\"hostname\":\"airlock\",\"label\":\"airlock-control\",\"tag\":\"airlock\",\"enable_ipv6\":true,\"backups\":\"disabled\"}" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('instance',{}).get('id') or d)"
    ID="$(instance_id)"
  fi
  echo ">> waiting for instance to go active…"
  for i in $(seq 1 60); do
    STATE=$(api "https://api.vultr.com/v2/instances/$ID" | python3 -c "import json,sys;i=json.load(sys.stdin)['instance'];print(i['status'],i['power_status'])")
    [ "$STATE" = "active running" ] && break; sleep 10
  done
  echo ">> instance $ID active at $(instance_ip)"

  # firewall: only 22/80/443 open; the app stays behind Caddy
  FW=$(api "https://api.vultr.com/v2/firewalls" | python3 -c "import json,sys;print(next((g['id'] for g in json.load(sys.stdin)['firewall_groups'] if g['description']=='$FW_GROUP'),''))")
  if [ -z "$FW" ]; then
    FW=$(api -X POST "https://api.vultr.com/v2/firewalls" -d "{\"description\":\"$FW_GROUP\"}" | python3 -c "import json,sys;print(json.load(sys.stdin)['firewall_group']['id'])")
    for RULE in '{"protocol":"tcp","port":"22","source":"0.0.0.0/0","subnet_size":0}' '{"protocol":"tcp","port":"80","source":"0.0.0.0/0","subnet_size":0}' '{"protocol":"tcp","port":"443","source":"0.0.0.0/0","subnet_size":0}' '{"protocol":"icmp","source":"0.0.0.0/0","subnet_size":0}'; do
      api -X POST "https://api.vultr.com/v2/firewalls/$FW/rules" -d "{\"ip_type\":\"v4\",$RULE}" > /dev/null
    done
  fi
  api -X POST "https://api.vultr.com/v2/firewall-group-update" -d "{\"instance_id\":\"$ID\",\"firewall_group_id\":\"$FW\"}" > /dev/null && echo ">> firewall $FW attached (22/80/443 only)"

  # Serverless Inference: subscription + key (raw responses printed — endpoint shapes
  # evolve; adapt here if the API answers differently). Guarded so retries never create
  # duplicate subscriptions.
  if [ ! -s "$INF_KEY_FILE" ]; then
    SUB=$(api "https://api.vultr.com/v2/inference" | python3 -c "import json,sys;s=json.load(sys.stdin).get('subscriptions',[]);print(s[0]['id'] if s else '')")
    if [ -z "$SUB" ]; then
      echo ">> creating inference subscription…"
      api -X POST "https://api.vultr.com/v2/inference" -d '{"label":"airlock"}'
      echo
      SUB=$(api "https://api.vultr.com/v2/inference" | python3 -c "import json,sys;s=json.load(sys.stdin).get('subscriptions',[]);print(s[0]['id'] if s else '')")
    fi
    echo ">> subscription: ${SUB:-<none>} — creating API key…"
    api -X POST "https://api.vultr.com/v2/inference/$SUB/api-keys" -d '{"label":"airlock-agents"}'
    echo
  fi
}

stage_server() {
  set -e
  IP=$(instance_ip); [ -n "$IP" ] || { echo "no instance — run infra first"; exit 1; }
  echo ">> rsync repo → $IP:/opt/airlock"
  rsync -a --delete -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new" \
    --exclude .venv --exclude .git --exclude web/node_modules --exclude web/.next \
    --exclude web/out --exclude .pytest_cache --exclude .mypy_cache --exclude .ruff_cache \
    --exclude airlock-store.db --exclude airlock.db --exclude .env \
    "$REPO_DIR/" "root@$IP:/opt/airlock/"

  echo ">> installing docker + gVisor (runsc)…"
  ssh_vm 'apt-get update -q && apt-get install -yq ca-certificates curl gnupg && curl -fsSL https://get.docker.com | sh && \
    curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release/main" > /etc/apt/sources.list.d/gvisor.list && \
    apt-get update -q && apt-get install -yq runsc && \
    python3 - <<PY
import json
d = json.load(open("/etc/docker/daemon.json")) if __import__("os").path.exists("/etc/docker/daemon.json") else {}
d.setdefault("runtimes", {})["runsc"] = {"path": "/usr/bin/runsc"}
json.dump(d, open("/etc/docker/daemon.json", "w"))
PY
    systemctl restart docker && docker run --rm --runtime=runsc hello-world > /dev/null 2>&1 && echo "runsc OK" || echo "runsc check skipped (hello-world pull needs egress)"'

  echo ">> building sandbox images on host (registry egress via squid at runtime)…"
  ssh_vm 'cd /opt/airlock && docker build -q -f deploy/sandbox_images/Dockerfile.python -t airlock-sandbox-python:1 . && docker build -q -f deploy/sandbox_images/Dockerfile.node -t airlock-sandbox-node:1 .'

  echo ">> writing .env and starting the stack"
  ADMIN=$(openssl rand -hex 24); SESSION=$(openssl rand -hex 32)
  if [ -s "$INF_KEY_FILE" ]; then MODE_PROD=1; else MODE_PROD=0; fi
  {
    echo "AIRLOCK_ENV=$([ "$MODE_PROD" = 1 ] && echo prod || echo staging)"
    echo "AIRLOCK_LLM_PROVIDER=$([ "$MODE_PROD" = 1 ] && echo vultr || echo dummy)"
    [ "$MODE_PROD" = 1 ] && echo "AIRLOCK_VULTR_INFERENCE_API_KEY=$(cat "$INF_KEY_FILE")"
    [ "$MODE_PROD" = 1 ] && echo "AIRLOCK_PLANNER_MODEL=${AIRLOCK_PLANNER_MODEL:-glm-5.3-flash}"
    [ "$MODE_PROD" = 1 ] && echo "AIRLOCK_CODER_MODEL=${AIRLOCK_CODER_MODEL:-qwen3.8-27b}"
    echo "AIRLOCK_SANDBOX_BACKEND=docker"
    echo "AIRLOCK_SANDBOX_RUNTIME=runsc"
    echo "AIRLOCK_BOOTSTRAP_ADMIN_KEY=$ADMIN"
    echo "AIRLOCK_SESSION_SECRET=$SESSION"
  } > /tmp/airlock.env
  scp -qi "$SSH_KEY" -o StrictHostKeyChecking=accept-new /tmp/airlock.env "root@$IP:/opt/airlock/.env" && shred /tmp/airlock.env
  umask 177; echo "$ADMIN" > "$HOME/.vultr/prod-admin-key"
  echo ">> admin key saved to ~/.vultr/prod-admin-key (shown once here): $ADMIN"

  ssh_vm 'cd /opt/airlock/deploy && docker compose up -d --build'
  echo ">> waiting for readyz…"
  for i in $(seq 1 30); do
    READY=$(curl -s -m 5 "http://$IP/readyz" || true)
    echo "$READY" | grep -q '"status":"ok"' && { echo ">> ready: $READY"; echo ">> public URL: http://$IP"; return 0; }
    sleep 5
  done
  echo "readyz did not turn green in 150s — check: ssh_vm 'cd /opt/airlock/deploy && docker compose logs api'"
}

stage_flip() {
  # models chosen by testing (never by name) — pass e.g.:
  #   scripts/vultr_deploy.sh flip glm-5.3-flash qwen3.8-27b
  set -e
  [ -s "$INF_KEY_FILE" ] || { echo "no inference key at $INF_KEY_FILE — run infra first"; exit 1; }
  PLANNER="${1:?planner model}"; CODER="${2:?coder model}"
  IP=$(instance_ip)
  scp -qi "$SSH_KEY" -o StrictHostKeyChecking=accept-new "$INF_KEY_FILE" "root@$IP:/root/inference-key"
  ssh_vm "cd /opt/airlock && chmod 600 /root/inference-key && sed -i \
    -e 's/^AIRLOCK_ENV=.*/AIRLOCK_ENV=prod/' \
    -e 's/^AIRLOCK_LLM_PROVIDER=.*/AIRLOCK_LLM_PROVIDER=vultr/' \
    -e '/^AIRLOCK_VULTR_INFERENCE_API_KEY/d' -e '/^AIRLOCK_PLANNER_MODEL/d' -e '/^AIRLOCK_CODER_MODEL/d' \
    .env && printf 'AIRLOCK_VULTR_INFERENCE_API_KEY=%s\nAIRLOCK_PLANNER_MODEL=%s\nAIRLOCK_CODER_MODEL=%s\n' \"\$(cat /root/inference-key)\" '$PLANNER' '$CODER' >> .env"
  ssh_vm 'cd /opt/airlock/deploy && docker compose up -d --force-recreate api'
  sleep 8
  echo ">> readyz now: $(curl -s -m 10 "http://$IP/readyz")"
}

stage_status() {
  ID=$(instance_id); echo "instance: ${ID:-none} @ $(instance_ip)"
  IP=$(instance_ip); [ -n "$IP" ] && { echo "readyz: $(curl -s -m 8 "http://$IP/readyz" || echo unreachable)"; echo "stats:  $(curl -s -m 8 "http://$IP/v1/stats" | head -c 200)"; }
}

case "${1:-}" in
  infra) stage_infra ;;
  server) stage_server ;;
  flip) shift; stage_flip "$@" ;;
  status) stage_status ;;
  *) echo "usage: vultr_deploy.sh infra|server|flip <planner> <coder>|status"; exit 2 ;;
esac
