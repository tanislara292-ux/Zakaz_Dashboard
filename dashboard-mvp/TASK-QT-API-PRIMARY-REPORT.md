# TASK-QT-API-PRIMARY — Result Summary

## Overview
Primary pipeline for ingesting QTickets sales and inventory data now reads directly from the official REST API. Google Sheets remains a manual fallback. The new integration lands raw data in ClickHouse staging tables, builds facts and dimensions for BI, and is orchestrated by systemd every 15 minutes.

## Items Delivered
- New Python module `integrations/qtickets_api/` with API client, transforms, inventory aggregation, configuration loader, and CLI entrypoint.
- ClickHouse migration `infra/clickhouse/migrations/2025-qtickets-api.sql` defining staging (`stg_qtickets_api_*`), facts (`fact_qtickets_sales_daily`, `fact_qtickets_inventory_latest`), refreshed `dim_events`, and BI views (`v_sales_latest`, `v_sales_14d`).
- Secrets template `configs/.env.qtickets_api.sample` and CLI options for custom env files.
- systemd unit/timer (`qtickets_api.service` / `qtickets_api.timer`) plus tooling updates in `ops/systemd/manage_timers.sh` and runbook documentation.
- Health monitoring: new `/healthz/qtickets_api` endpoint, meta_job_runs logging, smoke SQL (`infra/clickhouse/smoke_checks_qtickets_api.sql`), and alerting support for `status in ('error','failed')`.
- Documentation updates (`docs/RUNBOOK_INTEGRATIONS.md`, `docs/ARCHITECTURE.md`, DataLens docs) and dedicated module README.

## Technical Notes
- The loader loads configuration from `secrets/.env.qtickets_api`, instantiates `QticketsApiClient` with exponential backoff (429/5xx), collects events/orders/inventory, transforms to normalized rows (MSK timestamps), and writes staging + fact tables in one run. `_ver` (Unix timestamp per run) and `_dedup_key` guarantee idempotent inserts under ReplacingMergeTree.
- Inventory snapshots aggregate seat availability per show. Architecture is prepared for show-level API gaps—`build_inventory_snapshot` raises `NotImplementedError` if show IDs remain unavailable.
- Job status is recorded in `zakaz.meta_job_runs` with `status in ('ok','failed')`, metrics for sales/inventory counts, and error propagation on failure.
- Loader supports `--since-hours`, `--dry-run`, `--verbose`, `--envfile`, and optional `--ch-env` overrides.

## Warehouse Artefacts
- **Staging**: `zakaz.stg_qtickets_api_orders_raw`, `zakaz.stg_qtickets_api_inventory_raw`
- **Facts / Dimensions**: `zakaz.fact_qtickets_sales_daily`, `zakaz.fact_qtickets_inventory_latest`, `zakaz.dim_events`
- **Views for BI**: `zakaz.v_sales_latest`, `zakaz.v_sales_14d`
- Smoke validation script: `infra/clickhouse/smoke_checks_qtickets_api.sql`

## Monitoring & Operations
- Healthcheck handler `/healthz/qtickets_api` verifies that `fact_qtickets_sales_daily` and `fact_qtickets_inventory_latest` have data fresher than two hours.
- Alert manager now treats `status in ('error','failed')` as failure; `qtickets_api` job is visible in meta_job_runs dashboards.
- `ops/systemd/manage_timers.sh` installs and enables the new timer together with the service file; runbook documents enable/disable procedures and required secrets on the prod host.

## Testing Performed
- Static compilation check: `py -3 -m compileall integrations/qtickets_api`
- Manual dry-run instructions documented in module README (`python -m integrations.qtickets_api.loader --dry-run`). Execution restricted because external QTickets API credentials are not available in the local sandbox.
- Healthcheck and alert logic validated via unit-level reasoning (no live ClickHouse access in this environment); smoke SQL covers negative/positive constraints.

## Risks & Follow-up
1. **QTickets API rate limiting** — backoff implemented (1/2/4 seconds, 3 attempts). Need to monitor for 429 frequency once real credentials provided.
2. **show_id discovery gap** — vendor documentation still unclear; `build_inventory_snapshot` raises `NotImplementedError` when no shows detected. Coordination with QTickets support required to unlock per-show seat retrieval (temporary fallback: inventory remains empty).
3. **Token scope** — current bearer token grants organiser-level read access. Request read-only scope from QTickets if available; rotate token periodically and store in `secrets/.env.qtickets_api`.

## Next Steps
- Deploy migration `infra/clickhouse/migrations/2025-qtickets-api.sql` on production ClickHouse, then run loader with real credentials (remove `--dry-run`). 
- Add integration smoke tests in CI once credentials/test stubs are available (mock API or recorded fixtures).
- Monitor `/healthz/qtickets_api`, alert channel, and DataLens widgets to confirm the new fact tables feed dashboards correctly. If show inventory remains blocked, schedule vendor follow-up.
