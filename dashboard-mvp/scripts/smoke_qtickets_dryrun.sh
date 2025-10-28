#!/usr/bin/env bash
# Build and execute the QTickets API loader in DRY_RUN mode.
# The helper either reuses the provided env file or copies the sample template.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_SAMPLE_ENV="${PROJECT_ROOT}/configs/.env.qtickets_api.sample"
DEFAULT_NETWORK="clickhouse_default"

ENV_FILE=""
NETWORK="${DEFAULT_NETWORK}"
CONTAINER_ARGS=()
TEMP_ENV=""

cleanup() {
  if [[ -n "${TEMP_ENV}" && -f "${TEMP_ENV}" ]]; then
    rm -f "${TEMP_ENV}"
  fi
}
trap cleanup EXIT

usage() {
  cat <<EOF
Usage: $(basename "$0") [--env-file PATH] [--network NAME] [-- CONTAINER_ARGS...]

Defaults:
  --env-file <copy of configs/.env.qtickets_api.sample>
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

if [[ -z "${ENV_FILE}" ]]; then
  if [[ ! -f "${DEFAULT_SAMPLE_ENV}" ]]; then
    echo "ERROR: Sample env file not found at ${DEFAULT_SAMPLE_ENV}" >&2
    exit 1
  fi
  TEMP_ENV="$(mktemp)"
  cp "${DEFAULT_SAMPLE_ENV}" "${TEMP_ENV}"
  ENV_FILE="${TEMP_ENV}"
  echo "[smoke] Copied sample env to ${ENV_FILE}"
else
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: Env file not found: ${ENV_FILE}" >&2
    exit 1
  fi
fi

# Load integration env to reuse ClickHouse credentials for verification.
set -o allexport
source "${ENV_FILE}"
set +o allexport

: "${CLICKHOUSE_USER:?CLICKHOUSE_USER must be set in env file}"
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD must be set in env file}"
: "${CLICKHOUSE_DB:=zakaz}"
: "${JOB_NAME:=qtickets_api}"
: "${DRY_RUN:=true}"

dry_run_norm="$(echo "${DRY_RUN}" | tr '[:upper:]' '[:lower:]')"
if [[ "${dry_run_norm}" != "true" ]]; then
  echo "ERROR: DRY_RUN must be true for the smoke test (current value: ${DRY_RUN})." >&2
  exit 1
fi

wait_for_clickhouse() {
  echo "[smoke] Waiting for ClickHouse container ch-zakaz to become healthy..."
  local status="missing"
  for attempt in $(seq 1 60); do
    status="$(docker inspect -f '{{.State.Health.Status}}' ch-zakaz 2>/dev/null || echo "missing")"
    if [[ "${status}" == "healthy" ]]; then
      echo "[smoke] ClickHouse is healthy."
      return 0
    fi
    sleep 2
  done
  echo "ERROR: ClickHouse container health status is '${status}'. Ensure bootstrap_clickhouse.sh ran successfully." >&2
  exit 1
}

wait_for_clickhouse

job_name_sql=${JOB_NAME//\'/\'\'}

baseline_count="$(docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_USER}" \
  --password="${CLICKHOUSE_PASSWORD}" \
  -q "SELECT count() FROM ${CLICKHOUSE_DB}.meta_job_runs WHERE job = '${job_name_sql}'" || echo "__clickhouse_error__")"

if [[ "${baseline_count}" == "__clickhouse_error__" ]]; then
  echo "ERROR: Unable to read ${CLICKHOUSE_DB}.meta_job_runs with provided credentials (${CLICKHOUSE_USER})." >&2
  exit 1
fi

echo "[smoke] Existing meta_job_runs count for job='${JOB_NAME}': ${baseline_count}"

echo "[smoke] Building qtickets_api:latest image..."
docker build \
  -f "${PROJECT_ROOT}/integrations/qtickets_api/Dockerfile" \
  -t qtickets_api:latest \
  "${PROJECT_ROOT}"

echo "[smoke] Running dry-run container..."
set +e
docker run --rm \
  --network "${NETWORK}" \
  --env-file "${ENV_FILE}" \
  qtickets_api:latest \
  "${CONTAINER_ARGS[@]}"
exit_code=$?
set -e
echo "[smoke] Container exit code: ${exit_code}"

if [[ ${exit_code} -ne 0 ]]; then
  echo "ERROR: Dry-run container failed with exit code ${exit_code}." >&2
  exit ${exit_code}
fi

post_count="$(docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_USER}" \
  --password="${CLICKHOUSE_PASSWORD}" \
  -q "SELECT count() FROM ${CLICKHOUSE_DB}.meta_job_runs WHERE job = '${job_name_sql}'")"

recent_count="$(docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_USER}" \
  --password="${CLICKHOUSE_PASSWORD}" \
  -q "SELECT count() FROM ${CLICKHOUSE_DB}.meta_job_runs WHERE job = '${job_name_sql}' AND started_at >= subtractMinutes(now(), 5)")"

echo "[smoke] meta_job_runs count before run : ${baseline_count}"
echo "[smoke] meta_job_runs count after run  : ${post_count}"
echo "[smoke] meta_job_runs entries last 5min: ${recent_count}"

if [[ "${post_count}" != "${baseline_count}" ]]; then
  echo "ERROR: meta_job_runs count changed during DRY_RUN. Investigate before proceeding." >&2
  exit 1
fi

if [[ "${recent_count}" != "0" ]]; then
  echo "ERROR: Found ${recent_count} meta_job_runs records in the last 5 minutes. DRY_RUN should not write audit rows." >&2
  exit 1
fi

echo "[smoke] Latest meta_job_runs rows (expected empty for DRY_RUN):"
docker exec ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_USER}" \
  --password="${CLICKHOUSE_PASSWORD}" \
  -q "SELECT job, status, started_at, finished_at FROM ${CLICKHOUSE_DB}.meta_job_runs WHERE job = '${job_name_sql}' ORDER BY finished_at DESC LIMIT 5 FORMAT PrettyCompact"

echo "[smoke] Dry-run completed successfully with no ClickHouse writes."
