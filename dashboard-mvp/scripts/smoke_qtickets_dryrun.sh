#!/usr/bin/env bash
# Build and execute the QTickets API loader in dry-run mode.
# Defaults match a clean deployment where configs/.env.qtickets_api.sample is used.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_ENV_FILE="${PROJECT_ROOT}/configs/.env.qtickets_api.sample"
DEFAULT_NETWORK="clickhouse_default"

ENV_FILE="${DEFAULT_ENV_FILE}"
NETWORK="${DEFAULT_NETWORK}"
CONTAINER_ARGS=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [--env-file PATH] [--network NAME] [-- CONTAINER_ARGS...]

Defaults:
  --env-file ${DEFAULT_ENV_FILE}
  --network  ${DEFAULT_NETWORK}

Examples:
  $(basename "$0")
  $(basename "$0") --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api
  $(basename "$0") -- --verbose
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --env-file expects a path." >&2
        usage
        exit 1
      fi
      ENV_FILE="$2"
      shift 2
      ;;
    --network)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --network expects a name." >&2
        usage
        exit 1
      fi
      NETWORK="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      CONTAINER_ARGS=("$@")
      break
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: Env file not found: ${ENV_FILE}" >&2
  exit 1
fi

echo "[smoke] Building qtickets_api:latest image..."
docker build \
  -f "${PROJECT_ROOT}/integrations/qtickets_api/Dockerfile" \
  -t qtickets_api:latest \
  "${PROJECT_ROOT}"

echo "[smoke] Running dry-run container..."
docker run --rm \
  --network "${NETWORK}" \
  --env-file "${ENV_FILE}" \
  qtickets_api:latest \
  "${CONTAINER_ARGS[@]}"

echo "[smoke] Dry-run completed successfully."
