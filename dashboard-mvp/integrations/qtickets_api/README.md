# QTickets API Loader

The loader pulls sales and inventory data from the official QTickets REST API
and writes it to ClickHouse. A fully stubbed dry-run mode ships in the
repository so that a clean server can verify the deployment without touching
Python sources or live credentials.

## Prerequisites

1. ClickHouse is up via the instructions in `infra/clickhouse/README.md`. All
   QTickets tables (`stg_qtickets_api_*`, `fact_qtickets_*`, `meta_job_runs`,
   dashboards views) already exist thanks to `bootstrap_schema.sql`.
2. Docker is installed on the host executing the loader.

## Prepare environment file

Copy the sample dotenv and adjust only the secret fields if needed:

```bash
cd /opt/zakaz_dashboard/dashboard-mvp
cp configs/.env.qtickets_api.sample /opt/zakaz_dashboard/secrets/.env.qtickets_api
```

The sample uses:

- `DRY_RUN=true`
- `CLICKHOUSE_HOST=ch-zakaz`, `CLICKHOUSE_PORT=8123`, `CLICKHOUSE_DB=zakaz`,
  `CLICKHOUSE_USER=etl_writer`, `CLICKHOUSE_PASSWORD=EtL2024!Strong#Pass`
- A placeholder `QTICKETS_TOKEN=dryrun-token` and `ORG_NAME=stub_org`

These defaults are enough to run the dry-run smoke test without any edits. When
moving to production update only the token, organiser name, and optional
ClickHouse credentials.

## Build and run dry-run

```bash
cd /opt/zakaz_dashboard/dashboard-mvp

# Build image (~380 MB, Python 3.11-slim)
docker build \
  -f integrations/qtickets_api/Dockerfile \
  -t qtickets_api:latest \
  .

# Run with the shared docker network from ClickHouse
docker run --rm \
  --network clickhouse_default \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest
```

Expected behaviour:

- Logs mention stub mode, empty payloads, and zero rows transformed.
- No HTTP requests are sent to QTickets (all API calls are suppressed).
- No ClickHouse writes occur and `meta_job_runs` is untouched.
- Exit code is `0`.

If you prefer a one-liner, use `scripts/smoke_qtickets_dryrun.sh` (see below).

## Switching to production

1. Edit the dotenv: set `DRY_RUN=false`, populate a real
   `QTICKETS_TOKEN`/`ORG_NAME`, and specify the ClickHouse writer credentials
   used in production.
2. Re-run the container (optionally pass `--since-hours N` to override the
   lookback window) or schedule the command in cron/systemd.
3. Monitor logs for non-zero row counts and ensure the loader exits with code
   `0`. On success the loader records the run in `zakaz.meta_job_runs`.

The loader automatically retries transient **5xx** API errors (no retries for
4xx), deduplicates orders in memory, and writes into staging/fact tables using
the shared `integrations.common.ch` helpers. Every run inserts a structured
entry into `zakaz.meta_job_runs` containing the status, row counts, and (for
failures) `http_status`, `error_code`, and `request_id`.

## Order retrieval specifics

- Requests follow the official specification (see `qtickesapi.md`, section "Список заказов"):
  the `where` filter array and `orderBy` sort directive are JSON strings encoded
  in the GET query parameters when calling `/orders`.
- When GET continuously fails with retryable 5xx errors, the client triggers a
  compatibility POST fallback that sends the same filters as a JSON body so the
  legacy behaviour remains available during API outages.

Verify the production run directly in ClickHouse:

```bash
# Confirm that facts are populated
docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password=admin_pass \
  -q "SELECT count() AS rows FROM zakaz.fact_qtickets_sales_daily;"

# Inspect the latest job audit entries
docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password=admin_pass \
  -q "SELECT job, status, started_at, finished_at, message FROM zakaz.meta_job_runs ORDER BY finished_at DESC LIMIT 5;"
```

## Automation helper

`dashboard-mvp/scripts/smoke_qtickets_dryrun.sh` builds the image and executes
the container in dry-run mode while checking the exit code. This mirrors the
manual steps above and is safe to run on a clean host straight after cloning the
repository.

## Local debugging

Developers can run the loader directly with Python:

```bash
python -m integrations.qtickets_api.loader \
  --envfile /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  --dry-run \
  --verbose
```

Flags:

- `--since-hours N` — override lookback window (default `24`).
- `--offline-fixtures-dir PATH` — replay JSON fixtures without hitting the API.
- `--ch-env PATH` — optional ClickHouse dotenv overrides.

All logging is structured (JSON-friendly) and goes to stdout.
