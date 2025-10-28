# CI/CD Recommendations for Zakaz_Dashboard

## Mandatory CI Jobs

### 1. ClickHouse schema validation
```yaml
validate_clickhouse_schema:
  stage: validate
  image: python:3.11
  script:
    - python scripts/validate_clickhouse_schema.py
  allow_failure: false
```

### 2. Python bytecode compilation
```yaml
compile_python:
  stage: validate
  image: python:3.11
  script:
    - python -m compileall dashboard-mvp
  allow_failure: false
```

### 3. Unit tests
```yaml
unit_tests:
  stage: test
  image: python:3.11
  script:
    - cd dashboard-mvp/vk-python
    - python -m pytest
  artifacts:
    reports:
      junit: dashboard-mvp/vk-python/tests/results.xml
  allow_failure: false
```

### 4. Docker image build
```yaml
docker_build:
  stage: build
  image: docker:28.0.0
  services:
    - docker:28.0.0-dind
  script:
    - docker build --no-cache \
        -f dashboard-mvp/integrations/qtickets_api/Dockerfile \
        -t qtickets_api:${CI_COMMIT_SHA} .
  only:
    - main
    - develop
```

### 5. (Optional) Smoke run against ClickHouse
```yaml
smoke_qtickets_dry_run:
  stage: test
  image: python:3.11
  services:
    - name: clickhouse/clickhouse-server:24.8
  script:
    - dashboard-mvp/scripts/bootstrap_clickhouse.sh
    - dashboard-mvp/scripts/smoke_qtickets_dryrun.sh --env-file dashboard-mvp/test_env/.env.template
  allow_failure: true
```

## Developer Checklist

### Before committing
- [ ] `python scripts/validate_clickhouse_schema.py`
- [ ] `python -m compileall dashboard-mvp`
- [ ] `cd dashboard-mvp/vk-python && python -m pytest`
- [ ] `docker build --dry-run -f dashboard-mvp/integrations/qtickets_api/Dockerfile .`

### Before pushing to `main`
- [ ] All tests green locally (including smoke if ClickHouse is available)
- [ ] Docker image builds successfully
- [ ] No non-deterministic `PARTITION BY` expressions in DDL
- [ ] Configuration files (.env templates, CI variables) up to date

## Critical Issues Addressed

| Problem | Fix |
| --- | --- |
| Non-deterministic partitions (`today()`/`now()`) | Replaced with column-based partitions (`toYYYYMM(_loaded_at)` etc.) |
| Missing technical columns (`currency`, `_loaded_at`) | Added to tables with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` |
| Views referencing absent columns | Covered by `scripts/validate_clickhouse_schema.py` |
| Encoding issues in DDL files | Files converted to UTF-8; validator tolerates multiple encodings |

## Supporting Changes

1. **Static validator** `scripts/validate_clickhouse_schema.py`
   - Checks view ↔ table column consistency
   - Detects non-deterministic partitioning
   - Falls back to several encodings (`utf-8`, `utf-8-sig`, `cp1251`, `latin-1`)

2. **Test environment template** `dashboard-mvp/test_env/.env.template`
   - Provides defaults for smoke run in CI

3. **Infrastructure README (`infra/clickhouse/README.md`)**
   - Contains instructions to run schema validation prior to bootstrap

## Suggested CI Variables
```yaml
variables:
  CLICKHOUSE_VERSION: "24.8"
  PYTHON_VERSION: "3.11"
  DOCKER_TLS_VERIFY: "1"
```

Add secrets for ClickHouse credentials and third-party tokens via CI secret store; do not commit real `.env` files.

## Monitoring Targets
- Test coverage (goal ≥80%)
- Linter/static check violations (goal 0)
- Docker image build duration (goal ≤5 minutes)
- `validate_clickhouse_schema.py` runtime (goal ≤30 seconds)

## Security / Dependabot

- `pip-audit` on key `requirements.txt` (allow failure until pipeline stabilises).
- Container scan (Trivy or Clair) for produced images (allow failure but collect metrics).

## Deployment Strategy

| Environment | Trigger | Notes |
| --- | --- | --- |
| `develop` | Automatic after pipeline success | Ephemeral ClickHouse instance recommended |
| `staging` | Manual | Requires green pipeline + smoke |
| `production` | Manual with approval | Backup ClickHouse before deploy; keep last 5 images |

Rollback: fail health checks → automatic revert, or redeploy previous tag. Always take ClickHouse snapshots before production rollouts.

## Documentation Automation

- Generate changelog, API docs, and smoke reports as CI artifacts.
- Publish release notes to Confluence (or internal wiki) after production deployment.
