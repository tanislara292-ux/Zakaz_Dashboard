#!/bin/bash
# One-click deploy of Zakaz Dashboard services (systemd + timers + CH schema) without touching Apache.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MANAGE_TIMERS="${ROOT}/ops/systemd/manage_timers.sh"
HEALTH_UNIT_SRC="${ROOT}/ops/systemd/healthcheck.service"
HEALTH_UNIT_DST="/etc/systemd/system/healthcheck.service"
ENV_CH="${ROOT}/secrets/.env.ch"
CH_CONTAINER="${CH_CONTAINER:-ch-zakaz}"
QT_API_IMAGE="${QT_API_IMAGE:-qtickets_api:latest}"
REQUIRED_ENVS=(
  "$ENV_CH"
  "${ROOT}/secrets/.env.qtickets_api"
  "${ROOT}/secrets/.env.qtickets_sheets"
  "${ROOT}/secrets/.env.vk"
  "${ROOT}/secrets/.env.direct"
  "${ROOT}/secrets/.env.gmail"
  "${ROOT}/secrets/.env.alerts"
)

log()  { echo -e "\033[0;32m[INFO]\033[0m $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
fail() { echo -e "\033[0;31m[ERROR]\033[0m $*"; exit 1; }

require_root() {
  [[ $EUID -eq 0 ]] || fail "Run as root (sudo)."
}

ensure_envs() {
  local missing=()
  for f in "${REQUIRED_ENVS[@]}"; do
    [[ -f "$f" ]] || missing+=("$f")
  done
  if ((${#missing[@]})); then
    fail "Missing env files: ${missing[*]}"
  fi
}

ensure_files() {
  [[ -f "$MANAGE_TIMERS" ]] || fail "Missing $MANAGE_TIMERS."
  [[ -f "$HEALTH_UNIT_SRC" ]] || fail "Missing $HEALTH_UNIT_SRC."
}

load_clickhouse_env() {
  set -a
  source "$ENV_CH"
  set +a
  : "${CLICKHOUSE_HOST:?}" "${CLICKHOUSE_PORT:?}" "${CLICKHOUSE_USER:?}" "${CLICKHOUSE_PASSWORD:?}" "${CLICKHOUSE_DATABASE:?}"
}

check_clickhouse_health() {
  log "Checking ClickHouse container health ($CH_CONTAINER)..."
  local status
  status="$(docker inspect -f '{{.State.Health.Status}}' "$CH_CONTAINER" 2>/dev/null || echo "missing")"
  if [[ "$status" != "healthy" ]]; then
    fail "ClickHouse container $CH_CONTAINER is '$status'. Run scripts/bootstrap_clickhouse.sh first."
  fi
}

maybe_install_python() {
  if [[ -x "${ROOT}/.venv/bin/pip" ]]; then
    log "Installing Python deps into existing venv"
    "${ROOT}/.venv/bin/pip" install -r "${ROOT}/integrations/qtickets_api/requirements.txt"
    "${ROOT}/.venv/bin/pip" install -r "${ROOT}/ch-python/requirements.txt"
  else
    warn "No .venv found, skipping pip installs (assume system deps are satisfied)"
  fi
}

apply_clickhouse_schema() {
  log "Applying ClickHouse schema"
  docker exec -i "$CH_CONTAINER" clickhouse client \
    -u "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --multiquery \
    < "${ROOT}/infra/clickhouse/bootstrap_schema.sql"

  log "Applying ClickHouse roles (excluding XML-managed users)"
  grep -Ev "datalens_reader|etl_writer|backup_user" "${ROOT}/infra/clickhouse/bootstrap_roles_grants.sql" | \
    docker exec -i "$CH_CONTAINER" clickhouse client \
      -u "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --multiquery
}

build_qtickets_image() {
  log "Building QTickets API image: ${QT_API_IMAGE}"
  docker build -f "${ROOT}/integrations/qtickets_api/Dockerfile" -t "${QT_API_IMAGE}" "${ROOT}"
}

install_units() {
  log "Copying healthcheck unit"
  cp -f "$HEALTH_UNIT_SRC" "$HEALTH_UNIT_DST"

  log "Installing timers/services"
  bash "$MANAGE_TIMERS" install

  systemctl daemon-reload
  systemctl reset-failed healthcheck.service || true
}

enable_services() {
  log "Enabling healthcheck.service"
  systemctl enable --now healthcheck.service

  for t in qtickets_sheets qtickets qtickets_api vk_ads direct gmail alerts; do
    log "Enabling timer: $t"
    bash "$MANAGE_TIMERS" enable "$t"
    bash "$MANAGE_TIMERS" restart "$t"
  done
}

show_checks() {
  log "Healthcheck status:"
  systemctl status healthcheck.service --no-pager || true
  if command -v curl >/dev/null 2>&1; then
    curl -s http://localhost:18080/healthz | head || true
  fi
  log "Timers status:"
  bash "$MANAGE_TIMERS" status || true
}

main() {
  require_root
  ensure_envs
  ensure_files
  cd "$ROOT"
  load_clickhouse_env
  check_clickhouse_health
  maybe_install_python
  apply_clickhouse_schema
  build_qtickets_image
  install_units
  enable_services
  show_checks
  log "Install completed"
}

main "$@"
