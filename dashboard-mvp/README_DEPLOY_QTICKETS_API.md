# QTickets API Production Deployment

This playbook describes the exact sequence we use on the client's host after `git pull`. All commands assume the repository is synced to `/opt/zakaz_dashboard/dashboard-mvp`.

## 1. Prepare ClickHouse and Caddy

```bash
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
cp .env.example .env   # edit passwords/domains if required

# Fix permissions for ClickHouse run user (UID/GID 101 inside container)
chown -R 101:101 data logs caddy_data

# Start ClickHouse + Caddy reverse proxy
docker compose up -d

# Confirm containers are healthy
docker ps -a | grep ch-zakaz
```

The compose file exposes HTTP on `8123`, native protocol on `9000`, and Caddy on `8080/8443` by default. Adjust the `.env` file if you need alternative ports or domains.

## 2. Bootstrap the ClickHouse schema

Run the consolidated bootstrap script once after the containers are up. It applies the base schema, integrations, QTickets objects, and migrations in the correct order.

```bash
docker exec -i ch-zakaz clickhouse-client \
  --user="${CLICKHOUSE_ADMIN_USER:-admin}" \
  --password="${CLICKHOUSE_ADMIN_PASSWORD:-admin_pass}" \
  < /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/bootstrap_all.sql
```

Notes:
- The script creates a placeholder `datalens_reader` user if it is absent so that the GRANT statements succeed. Rotate the password afterwards if you rely on this account.
- Re-running the script is safe; objects are created with `IF NOT EXISTS` / idempotent DDL where possible.

## 3. Build the ingestion image

```bash
cd /opt/zakaz_dashboard
docker build \
  -f dashboard-mvp/integrations/qtickets_api/Dockerfile \
  -t qtickets_api:latest \
  dashboard-mvp
```

This installs Python dependencies from `integrations/qtickets_api/requirements.txt` and copies the entire repository into `/app` inside the image.

## 4. Environment configuration

Create `/opt/zakaz_dashboard/secrets/.env.qtickets_api` using the canonical variable names below. A ready-to-edit sample lives at `dashboard-mvp/test_env/.env.qtickets_api`.

```dotenv
QTICKETS_TOKEN=...                # production bearer token
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_SINCE_HOURS=4            # lookback window for orders
ORG_NAME=irs-prod

CLICKHOUSE_HOST=ch-zakaz
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=admin
CLICKHOUSE_PASSWORD=admin_pass
CLICKHOUSE_SECURE=false
CLICKHOUSE_VERIFY_SSL=false

TZ=Europe/Moscow
REPORT_TZ=Europe/Moscow
JOB_NAME=qtickets_api
DRY_RUN=true                       # override with false for production run
```

Legacy aliases such as `QTICKETS_API_TOKEN` or `CLICKHOUSE_DATABASE` remain supported, but the sample above is the single source of truth for future deployments.

## 5. Dry-run smoke (no ClickHouse writes)

```bash
docker run --rm \
  --network clickhouse_default \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest
```

With `DRY_RUN=true` the loader fetches data, prints detailed metrics, and skips ClickHouse writes (including `meta_job_runs`). Review container logs for `Dry-run complete`.

## 6. Production ingestion

```bash
docker run --rm \
  --network clickhouse_default \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  -e DRY_RUN=false \
  qtickets_api:latest
```

The job writes to staging, fact tables, and appends a record to `zakaz.meta_job_runs`.

## 7. Post-run verification

```bash
# Orders ingested
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count() AS orders_cnt FROM zakaz.stg_qtickets_api_orders_raw;"

# Dashboard view sample
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT * FROM zakaz.v_qtickets_sales_dashboard LIMIT 10;"

# Job registry
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT job, status, started_at, finished_at FROM zakaz.meta_job_runs ORDER BY finished_at DESC LIMIT 5;"
```

## 8. Troubleshooting

- **Permission denied on volumes** – ensure `chown -R 101:101 data logs caddy_data` ran before `docker compose up`.
- **GRANT failures during bootstrap** – the optional step is informative only. Create the accounts via `users.d/10-users.xml` or run the grants manually later.
- **ClickHouse connection from loader fails** – verify the container can resolve `ch-zakaz` (use the compose network) and that the environment variables match the ones in the `.env` file.
- **Docker build unavailable** – run `docker build` on any host with Docker Engine and push the resulting image to your registry; the loader only needs the environment values at runtime.

## 9. Reference assets

- `infra/clickhouse/.env.example` – template for compose variables
- `infra/clickhouse/bootstrap_all.sql` – canonical schema bootstrap
- `test_env/.env.qtickets_api` – sample loader environment
- `qtickets_debug/` – store ingestion run logs (`TASK-QT-API-PROD-FINAL-RUN.log`)
