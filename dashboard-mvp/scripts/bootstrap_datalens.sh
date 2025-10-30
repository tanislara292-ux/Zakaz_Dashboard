#!/usr/bin/env bash
# Validate DataLens read-only access against the local ClickHouse instance.
#
# Usage:
#   ./scripts/bootstrap_datalens.sh [--env-file PATH]
# Defaults to infra/clickhouse/.env for host/port and uses the static password
# from service user configuration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLICKHOUSE_DIR="${PROJECT_ROOT}/infra/clickhouse"
DEFAULT_ENV_FILE="${CLICKHOUSE_DIR}/.env"

ENV_FILE="${DEFAULT_ENV_FILE}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      shift
      [[ $# -gt 0 ]] || { echo "ERROR: --env-file requires argument" >&2; exit 1; }
      ENV_FILE="$1"
      shift
      ;;
    --help|-h)
      cat <<'EOF'
Usage: bootstrap_datalens.sh [--env-file PATH]

Checks DataLens connectivity by issuing HTTP queries via curl:
  * SELECT 1 for basic auth
  * Count tables in zakaz schema
  * SHOW GRANTS FOR datalens_reader
EOF
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: Env file not found: ${ENV_FILE}" >&2
  exit 1
fi

set -o allexport
source "${ENV_FILE}"
set +o allexport

: "${CLICKHOUSE_HTTP_PORT:=8123}"
: "${CLICKHOUSE_ADMIN_USER:=admin}"
: "${CLICKHOUSE_ADMIN_PASSWORD:=admin_pass}"

DL_USER="datalens_reader"
DL_PASSWORD="ChangeMe123!"
HOST="${CLICKHOUSE_HOST:-localhost}"
HTTP_PORT="${CLICKHOUSE_HTTP_PORT}"

BASE_URL="http://${HOST}:${HTTP_PORT}"

echo "[datalens] Checking SELECT 1 via HTTP..."
curl -fsSL -u "${DL_USER}:${DL_PASSWORD}" "${BASE_URL}/?query=SELECT%201" || {
  echo
  echo "ERROR: Unable to execute SELECT 1 as ${DL_USER}. Verify ClickHouse HTTP interface and credentials." >&2
  exit 1
}

echo
echo "[datalens] Counting zakaz tables..."
curl -fsSL -u "${DL_USER}:${DL_PASSWORD}" \
  "${BASE_URL}/?query=SELECT%20count()%20FROM%20system.tables%20WHERE%20database%3D'zakaz'" || {
  echo
  echo "ERROR: Unable to list zakaz tables as ${DL_USER}." >&2
  exit 1
}

echo
echo "[datalens] Showing grants for datalens_reader..."
docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD}" \
  -q "SHOW GRANTS FOR ${DL_USER};"

echo "[datalens] DataLens user verification completed."
