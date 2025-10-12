#!/usr/bin/env bash
set -euo pipefail

JOB_NAME="${1:?usage: run_job.sh <job> [--args...]}"
shift || true

# Загрузка окружения
source "$(dirname "$0")/../.env" 2>/dev/null || true

RUN_ID=$(python - <<'PY'
import uuid; print(uuid.uuid4())
PY
)
START_TS=$(date -Iseconds)

# Функции записи в meta.etl_runs
log_finish() {
  local status="$1"; local rows_written="$2"; local rows_read="$3"; local err="${4:-}"
  FINISH_TS=$(date -Iseconds)
  python - <<'PY'
import os, sys, json, socket
from clickhouse_connect import get_client
job = os.environ["JOB_NAME"]
run_id = os.environ["RUN_ID"]
started_at = os.environ["START_TS"]
finished_at = os.environ["FINISH_TS"]
status = os.environ["STATUS"]
rows_written = int(os.environ.get("ROWS_WRITTEN","0"))
rows_read    = int(os.environ.get("ROWS_READ","0"))
err_msg      = os.environ.get("ERR_MSG","")
from_date    = os.environ.get("FROM_DATE","1970-01-01")
to_date      = os.environ.get("TO_DATE","1970-01-01")
host         = socket.gethostname()
version_tag  = os.environ.get("GIT_COMMIT","local")
client = get_client(host=os.environ.get("CH_HOST","localhost"),
                    port=int(os.environ.get("CH_PORT","8123")),
                    username=os.environ.get("CH_USER","admin"),
                    password=os.environ.get("CH_PASSWORD",""),
                    database=os.environ.get("CH_DB","default"),
                    https=os.environ.get("CH_HTTPS","0")=="1")
client.command("""
INSERT INTO meta.etl_runs
(job, run_id, started_at, finished_at, status, rows_written, rows_read, err_msg, from_date, to_date, host, version_tag)
VALUES
(%(job)s, %(run_id)s, %(started_at)s, %(finished_at)s, %(status)s, %(rows_written)s, %(rows_read)s, %(err_msg)s, %(from_date)s, %(to_date)s, %(host)s, %(version_tag)s)
""", {
  "job": job, "run_id": run_id, "started_at": started_at, "finished_at": finished_at,
  "status": status, "rows_written": rows_written, "rows_read": rows_read, "err_msg": err_msg,
  "from_date": from_date, "to_date": to_date, "host": host, "version_tag": version_tag
})
PY
}

export JOB_NAME RUN_ID START_TS

# Разбор типовых задач
case "$JOB_NAME" in
  "vk_fetch")
    # пример: vk-python сбор сырых данных
    cd vk-python
    python -m vk_ads_pipeline.main --days "${DAYS:-2}" --sink clickhouse "$@"
    ROWS_WRITTEN=${ROWS_WRITTEN:-0}
    ;;

  "build_dm_sales")
    cd ch-python
    python cli.py build-dm-sales --days "${DAYS:-2}" "$@"
    ROWS_WRITTEN=${ROWS_WRITTEN:-0}
    ;;

  "build_dm_vk")
    cd ch-python
    python cli.py build-dm-vk --days "${DAYS:-2}" "$@"
    ROWS_WRITTEN=${ROWS_WRITTEN:-0}
    ;;

  "cdc_qtickets")
    cd ch-python
    python cli.py cdc-qtickets --minutes "${NRT_INTERVAL_MIN:-10}" "$@"
    ROWS_WRITTEN=${ROWS_WRITTEN:-0}
    ;;

  "cdc_vk")
    cd ch-python
    python cli.py cdc-vk --minutes "${NRT_INTERVAL_MIN:-10}" "$@"
    ROWS_WRITTEN=${ROWS_WRITTEN:-0}
    ;;

  "build_dm_sales_incr")
    cd ch-python
    python cli.py build-dm-sales-incr "$@"
    ROWS_WRITTEN=${ROWS_WRITTEN:-0}
    ;;

  "build_dm_vk_incr")
    cd ch-python
    python cli.py build-dm-vk-incr "$@"
    ROWS_WRITTEN=${ROWS_WRITTEN:-0}
    ;;

  "backfill_all")
    python ops/backfill.py "$@"
    ROWS_WRITTEN=${ROWS_WRITTEN:-0}
    ;;

  *)
    echo "Unknown job: $JOB_NAME" >&2
    exit 2
    ;;
esac

STATUS="ok"; ROWS_READ=${ROWS_READ:-0}
log_finish "$STATUS" "$ROWS_WRITTEN" "$ROWS_READ" ""