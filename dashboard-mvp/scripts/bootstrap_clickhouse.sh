#!/usr/bin/env bash
# Bootstrap a local ClickHouse instance for the Zakaz dashboard.
#
# Usage:
#   cd dashboard-mvp/infra/clickhouse
#   ../scripts/bootstrap_clickhouse.sh
#
# The script expects that .env has been prepared from .env.example.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLICKHOUSE_DIR="${PROJECT_ROOT}/infra/clickhouse"
ENV_FILE="${CLICKHOUSE_DIR}/.env"
SCHEMA_FILE="${CLICKHOUSE_DIR}/bootstrap_schema.sql"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} is missing. Copy infra/clickhouse/.env.example to .env first." >&2
  exit 1
fi

if [[ ! -f "${SCHEMA_FILE}" ]]; then
  echo "ERROR: ${SCHEMA_FILE} is missing. Ensure the repository is up to date." >&2
  exit 1
fi

# Load ClickHouse credentials and ports for later docker exec commands.
set -o allexport
source "${ENV_FILE}"
set +o allexport

: "${CLICKHOUSE_ADMIN_USER:=admin}"
: "${CLICKHOUSE_ADMIN_PASSWORD:=admin_pass}"
: "${CLICKHOUSE_DB:=zakaz}"

echo "[bootstrap] Preparing ClickHouse data directories..."
mkdir -p "${CLICKHOUSE_DIR}/data" "${CLICKHOUSE_DIR}/logs"

if command -v chown >/dev/null 2>&1; then
  if ! chown 101:101 "${CLICKHOUSE_DIR}/data" "${CLICKHOUSE_DIR}/logs" 2>/dev/null; then
    echo "[bootstrap] WARNING: Unable to chown directories to 101:101. Run the script with sufficient privileges if ClickHouse fails to start."
  fi
else
  echo "[bootstrap] WARNING: chown command not available; skipping ownership adjustment."
fi

# Select docker compose binary.
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif docker-compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "ERROR: docker compose command not found." >&2
  exit 1
fi

echo "[bootstrap] Starting ClickHouse via docker compose..."
(
  cd "${CLICKHOUSE_DIR}"
  "${COMPOSE_CMD[@]}" up -d
)

echo "[bootstrap] Waiting for container ch-zakaz to become healthy..."
for attempt in $(seq 1 60); do
  status="$(docker inspect -f '{{.State.Health.Status}}' ch-zakaz 2>/dev/null || echo "starting")"
  if [[ "${status}" == "healthy" ]]; then
    echo "[bootstrap] ClickHouse is healthy."
    break
  fi
  sleep 2
done

if [[ "${status}" != "healthy" ]]; then
  echo "ERROR: ClickHouse container health status is '${status}'. Check docker logs ch-zakaz for details." >&2
  exit 1
fi

echo "[bootstrap] Applying bootstrap_schema.sql..."
docker exec -i ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  < "${SCHEMA_FILE}"

echo "[bootstrap] Listing tables in ${CLICKHOUSE_DB}..."
docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  -q "SHOW TABLES FROM ${CLICKHOUSE_DB};"

echo "[bootstrap] Done. Optional grants can be applied with:"
echo "  docker exec -i ch-zakaz clickhouse-client --user=\"${CLICKHOUSE_ADMIN_USER}\" --password=\"${CLICKHOUSE_ADMIN_PASSWORD}\" < ${CLICKHOUSE_DIR}/bootstrap_grants.sql"

