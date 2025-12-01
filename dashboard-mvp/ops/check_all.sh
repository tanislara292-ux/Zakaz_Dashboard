#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANAGE_TIMERS="${ROOT}/ops/systemd/manage_timers.sh"

log() { echo -e "\033[0;32m[INFO]\033[0m $*"; }

log "Healthcheck status"
sudo systemctl status healthcheck.service --no-pager || true
if command -v curl >/dev/null 2>&1; then
  curl -s http://localhost:18080/healthz | head || true
  curl -s http://localhost:18080/healthz/detailed | head -n 5 || true
  curl -s http://localhost:18080/healthz/freshness | head -n 5 || true
fi

log "Timers status"
bash "$MANAGE_TIMERS" status || true

log "Recent ClickHouse job runs (if clickhouse-client inside container ch-zakaz)"
ADMIN_PASS=${ADMIN_PASS:-admin_pass}
docker exec -i ch-zakaz clickhouse client -u admin --password "$ADMIN_PASS" \
  --query "SELECT job,status,started_at,finished_at,message FROM zakaz.meta_job_runs ORDER BY started_at DESC LIMIT 15" || true
