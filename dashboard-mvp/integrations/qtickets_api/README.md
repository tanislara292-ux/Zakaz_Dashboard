# QTickets API Loader

Ingests QTickets sales and inventory data into ClickHouse. The module replaces
the legacy Google Sheets flow and can be executed locally or in Docker. A
dry‑run mode ships out of the box so that the deployment host never needs to
patch Python code.

## What You Get

- Docker image (`integrations/qtickets_api/Dockerfile`)
- DRY_RUN aware client that never hits the network without credentials
- Single entrypoint `integrations/qtickets_api/loader.py`
- Shared helpers in `integrations/common/*`

## Environment File

Use `configs/.env.qtickets_api.sample` as the template and copy it to the host,
for example `/opt/zakaz_dashboard/secrets/.env.qtickets_api`. The minimum set
of variables:

```dotenv
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_TOKEN=replace-with-organiser-token
QTICKETS_SINCE_HOURS=24
ORG_NAME=stub_org

CLICKHOUSE_HOST=ch-zakaz
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=replace-with-password
CLICKHOUSE_SECURE=false
CLICKHOUSE_VERIFY_SSL=false

TZ=Europe/Moscow
REPORT_TZ=Europe/Moscow
JOB_NAME=qtickets_api
DRY_RUN=true
```

Aliases such as `QTICKETS_API_TOKEN` are still recognised, but the canonical
keys above are preferred.

## Dry-Run Smoke

After cloning the repository and preparing ClickHouse (`infra/clickhouse`),
build and run the loader in dry-run mode:

```bash
docker build \
  -f dashboard-mvp/integrations/qtickets_api/Dockerfile \
  -t qtickets_api:latest \
  dashboard-mvp

docker run --rm \
  --network clickhouse_default \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --dry-run
```

Expected log lines:

- `QticketsApiClient initialized without org_name (stub mode). Requests will not hit real API.`
- `QticketsApiClient.list_events() stub for org=<missing_org> -> []`
- `[qtickets_api] Dry-run summary` with zero counts

The process exits with code `0` and never attempts to connect to ClickHouse
when `DRY_RUN=true`.

## Switching to Production

1. Flip `DRY_RUN=false` in the dotenv.
2. Populate real values for `QTICKETS_TOKEN`, `ORG_NAME`, and `CLICKHOUSE_*`.
3. Re-run the container (optionally with `--since-hours` to override the default
   lookback window).

The loader will:

- Fetch events and orders via the official API
- Transform payloads (`transform_orders_to_sales_rows`) into ClickHouse rows
- Load staging and fact tables (`stg_qtickets_api_*`, `fact_qtickets_*`)
- Record the run in `zakaz.meta_job_runs`

Failures are recorded unless the loader is executed with `--dry-run`.

## Local Invocation

For ad-hoc troubleshooting you can run the loader directly:

```bash
python -m integrations.qtickets_api.loader \
  --envfile secrets/.env.qtickets_api \
  --dry-run \
  --verbose
```

Additional flags:

- `--since-hours N` – override lookback window (default `24`)
- `--ch-env PATH` – optional ClickHouse dotenv override
- `--offline-fixtures-dir PATH` – replay JSON fixtures instead of real API calls

## Logging & Monitoring

Structured logs go to stdout. The following metrics are useful:

- `[qtickets_api] Dry-run summary` – zero rows in smoke mode
- `Starting QTickets API ingestion run` – includes job name, lookback window, dry run flag
- `Finished ingesting QTickets API payloads` – successful load with row counts
- `Skipping failure recording because the loader was invoked with --dry-run` – expected when DRY_RUN is enabled

All ClickHouse operations happen via the shared `integrations.common.ch`
helpers, so credentials never need to be hard-coded in the loader.
