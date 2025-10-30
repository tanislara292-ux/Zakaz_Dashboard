# CHANGELOG-015 — ClickHouse RBAC & QTickets hardening

## ClickHouse

- Introduced canonical XML layout:
  - `users.d/00-admin.xml` – admin with `GRANT ALL ON *.* WITH GRANT OPTION`.
  - `users.d/10-service-users.xml` – service accounts + profiles/quotas.
- Split bootstrap into `bootstrap_schema.sql` (DDL only) and
  `bootstrap_roles_grants.sql` (roles + privileges, idempotent).
- Removed `admin_min` and legacy grants from DDL files.
- Updated `scripts/bootstrap_clickhouse.sh` to apply roles and print
  `SHOW GRANTS` for `admin` / `datalens_reader`.
- Added `scripts/bootstrap_datalens.sh` for HTTP-level verification.

## QTickets Loader

- Reworked HTTP client logging:
  - Masked token fingerprints in metrics.
  - No retries for 4xx, retries only for 5xx/network errors.
  - Structured error context (`http_status`, `code`, `request_id`,
    `body_preview`).
- Dry-run mode short-circuits HTTP calls explicitly.
- `meta_job_runs` entries now include status + error metadata; failures use
  status `error`.
- Added unit tests for retry/stub behaviour (`tests/test_client.py`).

## Tooling & CI

- New GitHub Actions workflow (`.github/workflows/ci.yml`): schema validation,
  pytest, Docker build.
- `scripts/validate_clickhouse_schema.py` checks grant targets and required
  system tables.
- Added `secrets/README.md` documenting secret management, removed
  `secrets/ACCESS.md` from the repo.
- Archived outdated deployment scripts (`archive/outdated/`).

## Documentation

- Rewrote `README.md` with the new bootstrap flow, secrets policy, and CI badge.
- Added `docs/DEPLOYMENT.md` – copy-paste deployment playbook.
- Updated integration README/checklists to use `etl_writer` credentials.
