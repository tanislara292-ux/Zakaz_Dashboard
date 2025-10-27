# QTickets API Deployment Guide

This guide describes how to deploy and run the QTickets API integration service.

## Prerequisites

- Docker and Docker Compose installed
- ClickHouse server running and accessible
- QTickets API token and credentials

## Environment Configuration

The service can be configured either via a `.env` file or directly through environment variables.

### Option A: Using Environment File

Create a file `/run/secrets/.env.qtickets_api` with the following content:

```dotenv
# ==== QTickets API ====
QTICKETS_TOKEN=your_bearer_token_here
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_SINCE_HOURS=4
ORG_NAME=irs-prod

# ==== ClickHouse ====
CLICKHOUSE_HOST=ch-zakaz
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=admin_min
CLICKHOUSE_PASSWORD=AdminMin2024!Strong#Pass
CLICKHOUSE_SECURE=false
CLICKHOUSE_VERIFY_SSL=false

# ==== Runtime / service ====
TZ=Europe/Moscow
REPORT_TZ=Europe/Moscow
JOB_NAME=qtickets_api
DRY_RUN=false
```

### Option B: Using Environment Variables (Recommended for Production)

Pass all variables directly as `-e` flags to `docker run`.

## Building the Docker Image

```bash
docker build \
  -f dashboard-mvp/integrations/qtickets_api/Dockerfile \
  -t qtickets_api:latest \
  dashboard-mvp
```

## Running the Service

### Method 1: With Environment File

```bash
docker run --rm \
  --network clickhouse_default \
  -v /path/to/.env.qtickets_api:/run/secrets/.env.qtickets_api:ro \
  qtickets_api:latest
```

### Method 2: With Environment Variables (Recommended)

```bash
docker run --rm \
  --network clickhouse_default \
  -e QTICKETS_TOKEN='your_bearer_token_here' \
  -e QTICKETS_BASE_URL='https://qtickets.ru/api/rest/v1' \
  -e QTICKETS_SINCE_HOURS='4' \
  -e ORG_NAME='irs-prod' \
  -e CLICKHOUSE_HOST='ch-zakaz' \
  -e CLICKHOUSE_PORT='8123' \
  -e CLICKHOUSE_DB='zakaz' \
  -e CLICKHOUSE_USER='admin_min' \
  -e CLICKHOUSE_PASSWORD='AdminMin2024!Strong#Pass' \
  -e CLICKHOUSE_SECURE='false' \
  -e CLICKHOUSE_VERIFY_SSL='false' \
  -e TZ='Europe/Moscow' \
  -e REPORT_TZ='Europe/Moscow' \
  -e JOB_NAME='qtickets_api' \
  -e DRY_RUN='false' \
  qtickets_api:latest
```

## Dry Run Mode

To test the service without writing to ClickHouse:

```bash
docker run --rm \
  --network clickhouse_default \
  -e QTICKETS_TOKEN='your_bearer_token_here' \
  -e QTICKETS_BASE_URL='https://qtickets.ru/api/rest/v1' \
  -e QTICKETS_SINCE_HOURS='4' \
  -e ORG_NAME='irs-prod' \
  -e CLICKHOUSE_HOST='ch-zakaz' \
  -e CLICKHOUSE_PORT='8123' \
  -e CLICKHOUSE_DB='zakaz' \
  -e CLICKHOUSE_USER='admin_min' \
  -e CLICKHOUSE_PASSWORD='AdminMin2024!Strong#Pass' \
  -e CLICKHOUSE_SECURE='false' \
  -e CLICKHOUSE_VERIFY_SSL='false' \
  -e TZ='Europe/Moscow' \
  -e REPORT_TZ='Europe/Moscow' \
  -e JOB_NAME='qtickets_api' \
  -e DRY_RUN='true' \
  qtickets_api:latest
```

## Verifying Data in ClickHouse

After running the service, verify the data was loaded correctly:

```sql
-- Check raw orders
SELECT COUNT(*) FROM zakaz.stg_qtickets_api_orders_raw;

-- Check inventory data
SELECT COUNT(*) FROM zakaz.stg_qtickets_api_inventory_raw;

-- Check aggregated data
SELECT * FROM zakaz.v_qtickets_sales_dashboard LIMIT 10;

-- Check job run history
SELECT * FROM zakaz.meta_job_runs 
WHERE job = 'qtickets_api' 
ORDER BY started_at DESC 
LIMIT 5;
```

## Expected Log Output

### Successful Run (Dry Run)

```
INFO - Starting QTickets API ingestion run
INFO - Fetched events: 25
INFO - Fetched orders: 142
INFO - Built inventory snapshot: 25 events
INFO - Dry-run complete, no data written to ClickHouse
[qtickets_api] Dry-run complete:
  Events: 25
  Orders: 142
  Sales rows: 142
  Inventory shows processed: 25
```

### Successful Run (Production)

```
INFO - Starting QTickets API ingestion run
INFO - Fetched events: 25
INFO - Fetched orders: 142
INFO - Built inventory snapshot: 25 events
INFO - Успешная вставка 142 строк в таблицу zakaz.stg_qtickets_api_orders_raw
INFO - Успешная вставка 25 строк в таблицу zakaz.stg_qtickets_api_inventory_raw
INFO - Успешная вставка 25 строк в таблицу zakaz.dim_events
INFO - Успешная вставка 142 строк в таблицу zakaz.fact_qtickets_sales_daily
INFO - Успешная вставка 25 строк в таблицу zakaz.fact_qtickets_inventory_latest
INFO - [qtickets_api] Ingestion completed successfully
```

### ClickHouse Connection Error (Handled Gracefully)

```
ERROR - [qtickets_api] Failed to write to ClickHouse: Connection refused
ERROR - could not connect to ClickHouse: [Errno 111] Connection refused
```

## Troubleshooting

### Permission Denied on Secret File

If using the secret file method and getting permission errors, either:
1. Run the container as root: `docker run --user root ...`
2. Or use the environment variables method (recommended)

### ClickHouse Connection Issues

- Verify `CLICKHOUSE_HOST` and `CLICKHOUSE_PORT` are correct
- Ensure `CLICKHOUSE_SECURE` matches your ClickHouse setup (false for HTTP, true for HTTPS)
- Check network connectivity between container and ClickHouse

### API Authentication Issues

- Verify `QTICKETS_TOKEN` is correct and includes "Bearer " prefix if required
- Check `QTICKETS_BASE_URL` is accessible from the container