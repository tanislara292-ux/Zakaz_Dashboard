# Zakaz Dashboard

[![CI](https://github.com/zakaz-dashboard/Zakaz_Dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/zakaz-dashboard/Zakaz_Dashboard/actions/workflows/ci.yml)

Unified repository for the Zakaz analytics stack:

- **ClickHouse** (Docker) with prebuilt schemas, roles and service accounts.
- **QTickets API loader** (Python + Docker) for sales/inventory ingestion.
- **Yandex DataLens** read-only user and views for BI dashboards.
- Tooling, runbooks and smoke-tests to keep the pipeline reproducible.

---

## Quickstart

```bash
git clone <repository_url> Zakaz_Dashboard
cd Zakaz_Dashboard/dashboard-mvp/infra/clickhouse
cp .env.example .env

# 1. Start ClickHouse (schema + roles + grants)
../../scripts/bootstrap_clickhouse.sh

# 2. (Optional) Verify the DataLens reader via HTTP + SHOW GRANTS
../../scripts/bootstrap_datalens.sh

# 3. Run the QTickets dry-run smoke test (no writes)
cd ../..
./scripts/smoke_qtickets_dryrun.sh

# 4. Build the production loader image
docker build -f integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# 5. Launch ingestion (requires real .env with DRY_RUN=false)
docker run --rm \
  --network clickhouse_default \
  --env-file secrets/.env.qtickets_api \
  qtickets_api:latest
```

### Secrets

- Real tokens and passwords live **outside** the repository.
- Use your team password manager / secret store and drop runtime overrides into
  `secrets/.env.*` (see `secrets/README.md`).
- Default passwords in the repo are placeholders:
  - `admin / admin_pass`
  - `etl_writer / EtL2024!Strong#Pass`
  - `datalens_reader / ChangeMe123!` (rotate before production!)
  - `backup_user / Backup2024!Strong#Pass`

### ClickHouse operations

- Configuration lives in `infra/clickhouse/`:
  - `users.d/00-admin.xml` – admin with `GRANT ALL ON *.* WITH GRANT OPTION`.
  - `users.d/10-service-users.xml` – service accounts (writer, backup, DataLens).
  - `bootstrap_schema.sql` – pure DDL.
  - `bootstrap_roles_grants.sql` – canonical roles & privileges (idempotent).
- Detailed instructions: `infra/clickhouse/README.md`.

### QTickets loader

- Code: `integrations/qtickets_api/`.
- Environment template: `configs/.env.qtickets_api.sample` (uses `etl_writer`).
- Entry point: `integrations.qtickets_api.loader` (supports `--dry-run`).
- Logs & meta audit go to `zakaz.meta_job_runs` with structured payloads
  (`status`, `http_status`, `request_id`, etc.).

#### Important: API Token Requirements
The QTickets API requires specific scopes for different endpoints:
- **Events endpoint:** Requires `events:read` scope (working)
- **Orders endpoint:** Requires `orders:read` scope (must be requested from QTickets)
- **Mandatory filter:** Orders API requires `payed=1` filter to return actual sales data

See [ADR-035](docs/adr/ADR-035.md) for technical details about the payed=1 filter implementation.

### Testing & CI

- `python scripts/validate_clickhouse_schema.py` – static schema checker
  (validates views, partitions, and grant targets).
- `pytest integrations/qtickets_api/tests` – unit tests for transforms & API client.
- `docker build -f integrations/qtickets_api/Dockerfile .` – reproducible image build.
- GitHub Actions (`.github/workflows/ci.yml`) runs all the steps above on every
  push / pull request.

### Useful docs

- `infra/clickhouse/README.md` – deployment & RBAC reference.
- `docs/ARCHITECTURE.md` – high-level system diagram.
- `docs/DATALENS_CONNECTION_PLAN.md` – BI setup checklist.
- `docs/RUNBOOK_INTEGRATIONS.md` – operational playbooks.
- `docs/changelog/` – per-epic change history (remember to update when shipping).

---

## Next steps

1. Populate `secrets/.env.qtickets_api` with production tokens (keep it private).
2. Run the full bootstrap + smoke flow on a clean host.
3. Switch `DRY_RUN=false` and launch the loader container on schedule.
4. Connect DataLens using `datalens_reader` and validate dashboards.
5. Monitor `zakaz.meta_job_runs` and CI status for regressions.
