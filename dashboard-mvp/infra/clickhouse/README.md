# ClickHouse Stack

This directory contains the ClickHouse footprint required for the Zakaz
dashboard deployment. The stack must come up on a clean host without any manual
patching.

## Layout

- `docker-compose.yml` – ClickHouse service (add TLS proxy via override if needed)
- `.env.example` – sample compose configuration
- `config.d/`, `users.d/` – ClickHouse server configuration
- `migrations/`, `init*.sql`, `smoke_checks*.sql` – DDL and validation queries
- `bootstrap_all.sql` – single-shot initializer that applies every script in the
  correct order
- `data/`, `logs/`, `caddy_data/` – runtime directories (kept empty in git with
  `.gitkeep` placeholders; `caddy_data` is only needed when HTTPS proxying is enabled)

## Quick Start

```bash
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse

# 1. Compose environment
cp .env.example .env

# 2. Prepare filesystem permissions for ClickHouse UID 101
sudo chown -R 101:101 data logs
# Optional: chown caddy_data if you re-enable the TLS proxy
sudo chown -R 101:101 caddy_data

# 3. Launch ClickHouse (no TLS proxy by default)
docker compose up -d clickhouse
docker ps --filter name=ch-zakaz

# 4. Apply all schemas, views, and grants
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='admin_pass' \
  < /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/bootstrap_all.sql
```

The grants section automatically creates a `datalens_reader` user with a
placeholder password (`datalens_reader_placeholder`). Rotate the secret or
replace the user with the XML definition from `users.d/10-users.xml` if a custom
credential is required. The bundled `admin` account ships with
`access_management=1`, so it can execute the bootstrap script (including `GRANT`
statements) without manual XML edits.

## Smoke Checks

After the bootstrap script completes, run the smoke checks to ensure the
baseline objects exist:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password='admin_pass' \
  -q "SELECT name FROM system.tables WHERE database = 'zakaz' ORDER BY name"

docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password='admin_pass' \
  < /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/smoke_checks_qtickets_api.sql
```

## Reset / Tear Down

- `docker compose down` – stop services, keep volumes
- `docker compose down -v` – stop services and remove data directories (only use
  in non-production environments)

Re-run the Quick Start section afterwards to recreate the stack. Ensure the
permissions command is executed each time directories are recreated.

## Optional HTTPS Proxy

If HTTPS is required, add the `caddy` service via a compose override and expose
ports 8080/8443 accordingly. Use the bundled `Caddyfile` as the reference
configuration.
