# QTickets API Integration

This module ingests sales and inventory data from the official QTickets REST API into ClickHouse. It replaces the legacy Google Sheets flow (`integrations/qtickets_sheets`) and is scheduled to run every 15 minutes in production.

## Prerequisites

1. Request an organiser API token from the QTickets web console:  
   **Настройки → Основное → API → Сгенерировать токен.**
2. Copy the token to the production server and place it into `secrets/.env.qtickets_api` using the template below.
3. Ensure the ClickHouse writer credentials (`etl_writer`) are available in the same dotenv file or in `secrets/.env.ch`.

## Environment Variables

Create `configs/.env.qtickets_api.sample` (see template in this repository) and copy it to `secrets/.env.qtickets_api` on the server with production values.

Required keys:

```
QTICKETS_API_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_API_TOKEN=<organiser_bearer_token>
CLICKHOUSE_HOST=https://<caddy_host>:8443
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=<password>
CLICKHOUSE_DB=zakaz
TZ=Europe/Moscow
ORG_NAME=<organiser_name_for_logs>
```

## Manual Execution (Smoke Run)

```bash
python -m integrations.qtickets_api.loader \
  --envfile secrets/.env.qtickets_api \
  --since-hours 24 \
  --dry-run \
  --verbose
```

Remove `--dry-run` to persist data into ClickHouse. Use `--since-hours` to expand the lookback window (default = 24 hours).

## Log Interpretation

- `Starting QTickets API ingestion run` — loader initialises the ingestion window and version.
- `Fetched events/orders...` — API client retrieved payloads from the vendor.
- `Transformed orders into sales rows` — data prepared for ClickHouse staging.
- `Inventory snapshot skipped` — the API did not expose show IDs; investigate with QTickets support.
- Errors with `Temporary QTickets API error` indicate transient 429/5xx responses handled with retry/backoff.

## Verifying ClickHouse Data

After a successful non-dry-run execution run the following checks:

```sql
SELECT count(), max(sale_ts) FROM zakaz.fact_qtickets_sales_daily;
SELECT city, sum(tickets_left) FROM zakaz.fact_qtickets_inventory_latest GROUP BY city ORDER BY city;
SELECT * FROM zakaz.meta_job_runs WHERE job = 'qtickets_api' ORDER BY started_at DESC LIMIT 5;
```

`fact_qtickets_sales_daily` should contain the latest sales dates, and `fact_qtickets_inventory_latest` should have non-negative ticket balances. Job metadata is recorded in `zakaz.meta_job_runs` for monitoring.
