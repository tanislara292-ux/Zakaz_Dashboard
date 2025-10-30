# Deployment Playbook

This guide describes the end-to-end procedure for bringing a clean host to a
production-ready state: ClickHouse, QTickets ingestion, and DataLens.

---

## 0. Prerequisites

- Ubuntu host with Docker Engine ≥ 24 and Docker Compose v2.
- Git, curl.
- Access to the organisation secret store containing:
  - Production QTickets token.
  - ClickHouse passwords (etl_writer, datalens_reader, backup_user if rotated).
- DNS / HTTPS configuration for the ClickHouse endpoint (optional but
  recommended for DataLens).

## 1. Checkout & configuration

```bash
git clone <repository_url> /opt/zakaz_dashboard
cd /opt/zakaz_dashboard/Zakaz_Dashboard/dashboard-mvp

# ClickHouse env (used by docker-compose)
cd infra/clickhouse
cp .env.example .env
```

> The default credentials are placeholders. Rotate them before production if
> required and update `users.d/10-service-users.xml`.

## 2. Bootstrap ClickHouse

```bash
cd /opt/zakaz_dashboard/Zakaz_Dashboard/dashboard-mvp/infra/clickhouse
../../scripts/bootstrap_clickhouse.sh
```

The helper:

1. Creates `data/` and `logs/` with the correct UID.
2. Starts the ClickHouse container and waits until it is `healthy`.
3. Applies `bootstrap_schema.sql`.
4. Applies `bootstrap_roles_grants.sql`.
5. Prints `SHOW TABLES` for `zakaz` and `SHOW GRANTS` for `admin` /
   `datalens_reader`.

If any step fails, inspect `docker logs ch-zakaz` and re-run the script; it is
idempotent.

## 3. Verify DataLens reader

```bash
/opt/zakaz_dashboard/Zakaz_Dashboard/dashboard-mvp/scripts/bootstrap_datalens.sh
```

The script performs:

- `curl` requests as `datalens_reader`.
- `SHOW GRANTS FOR datalens_reader`.

If HTTPS is exposed, test with the public endpoint as well.

## 4. Prepare QTickets environment

```bash
cd /opt/zakaz_dashboard/Zakaz_Dashboard/dashboard-mvp
cp configs/.env.qtickets_api.sample secrets/.env.qtickets_api
vi secrets/.env.qtickets_api  # populate QTICKETS_TOKEN, ORG_NAME, ClickHouse host
```

- Use `etl_writer` credentials for ClickHouse access.
- Keep `DRY_RUN=true` for smoke tests; set to `false` only for production runs.

## 5. Smoke test (dry-run)

```bash
./scripts/smoke_qtickets_dryrun.sh --env-file secrets/.env.qtickets_api
```

Expected results:

- Container exit code `0`.
- No rows inserted into `zakaz.meta_job_runs`.
- Logs mention stub mode (no outbound HTTP calls).

## 6. Build production image

```bash
docker build \
  -f integrations/qtickets_api/Dockerfile \
  -t qtickets_api:prod \
  .
```

## 7. Production ingestion run

1. Edit `secrets/.env.qtickets_api` – set `DRY_RUN=false`, ensure real tokens.
2. Run the container:

```bash
docker run --rm \
  --network clickhouse_default \
  --env-file secrets/.env.qtickets_api \
  --name qtickets_api_run_$(date +%Y%m%d%H%M%S) \
  qtickets_api:prod
```

3. Verify ClickHouse:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT status, message FROM zakaz.meta_job_runs ORDER BY finished_at DESC LIMIT 5 FORMAT PrettyCompact"
```

4. Inspect staging/fact tables (sales/inventory) and confirm non-zero row counts.

## 8. DataLens

1. Change `datalens_reader` password (`ALTER USER ...`) or edit
   `users.d/10-service-users.xml` and restart the container.
2. Configure the connection in Yandex DataLens:
   - Host: ClickHouse HTTP endpoint.
   - Port: `8123` (or HTTPS proxy).
   - Database: `zakaz`.
   - User: `datalens_reader`.
3. Build dashboards from the `bi.*` / `zakaz.*` views.

## 9. Monitoring

- `zakaz.meta_job_runs` — ingestion status, rows processed, structured errors.
- `meta.backup_runs` — backup job audit trail.
- GitHub Actions (`CI` workflow) — schema validator, pytest and Docker build.
- Optional: export metrics to your observability stack (Grafana/Prometheus).

## 10. Troubleshooting

| Scenario | Checklist |
| --- | --- |
| `ACCESS_DENIED` during bootstrap | Ensure `users.d/00-admin.xml` is mounted and `admin` exists. Check `SHOW GRANTS FOR admin`. |
| Loader exits with `QticketsApiError` | Inspect `zakaz.meta_job_runs` message JSON for `http_status`, `code`, `request_id`. Re-run with higher log level (`--verbose`). |
| DataLens cannot connect | Run `scripts/bootstrap_datalens.sh`, confirm HTTP endpoint is reachable, rotate password if necessary. |
| Dry-run writes data | Verify `DRY_RUN=true` in `.env.qtickets_api`. The loader should skip ClickHouse writes when dry-run. |

---

Keep this guide in sync with automation changes (bootstrap scripts, CI, loader
behaviour). Update `docs/changelog/` when shipping notable infrastructure changes.
