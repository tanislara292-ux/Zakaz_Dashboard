# ADR-005: ClickHouse Production Hardening - Canonical Schema Enforcement
**Date:** 2025-10-28
**Status:** Accepted

## Context
Despite Task 004 completion, the repository still contains multiple conflicting DDL definitions for ClickHouse objects, particularly `zakaz.dim_events`. Bootstrap continues to fail with "Unknown expression 'start_date'" errors because old schemas using `event_date` coexist with new canonical structure using `start_date`, `end_date`, `_loaded_at`, `_ver`.

Multiple CREATE TABLE definitions exist across 7+ SQL files:
- `bootstrap_schema.sql`
- `bootstrap_all.sql`
- `init_integrations.sql`
- `init_qtickets_sheets.sql`
- `migrations/2025-qtickets-api-final.sql`
- `migrations/2025-qtickets-api.sql`
- `migrations/2025-qtickets-api.LOCAL.sql`

Additionally, dependent objects (views, materialized views, integration tables) still reference old column sets, preventing clean deployment.

## Decision
We will enforce a single canonical ClickHouse schema by:

1. **Canonical object definitions** - Retain exactly one CREATE TABLE definition per object aligned with the domain model
2. **Strategic DROP/CREATE sequence** - Insert DROP TABLE IF EXISTS before canonical CREATE to guarantee correct structure
3. **Comprehensive dependency updates** - Update all views, materialized views, and integration tables to use canonical columns
4. **Deterministic clauses enforcement** - Ensure all PARTITION BY, ORDER BY, TTL clauses use column expressions, not functions like `today()`
5. **Bootstrap script hardening** - Clean all bootstrap scripts to reference only canonical definitions

## Data Contracts

### Canonical dim_events Schema
```sql
CREATE TABLE IF NOT EXISTS zakaz.dim_events (
    event_id      String,                    -- Event identifier
    event_name    String,                    -- Event name
    city          LowCardinality(String),    -- City (lowercase, normalized)
    start_date    Nullable(Date),            -- Event start date
    end_date      Nullable(Date),            -- Event end date
    tickets_total UInt32 DEFAULT 0,          -- Latest total tickets
    tickets_left  UInt32 DEFAULT 0,          -- Latest available tickets
    _ver          UInt64,                    -- Version for ReplacingMergeTree
    _loaded_at    DateTime DEFAULT now()     -- Load timestamp
)
ENGINE = ReplacingMergeTree(_ver)
PARTITION BY tuple()
ORDER BY (event_id)
SETTINGS index_granularity = 8192;
```

### Key Standardizations
- **Date fields**: Use `start_date`/`end_date` instead of `event_date`
- **City fields**: Use `LowCardinality(String)` with lowercase normalization
- **Versioning**: Use `_ver` (UInt64) for ReplacingMergeTree
- **Audit**: Use `_loaded_at` (DateTime DEFAULT now()) for load tracking
- **Partitioning**: Use deterministic expressions, not `today()`/`now()`

## Risks

1. **Data loss risk** - DROP TABLE statements will remove existing data during re-deployment
2. **Consumer impact** - Downstream BI tools may need updates for new column names
3. **Migration complexity** - Need to coordinate with data consumers before production changes
4. **Testing overhead** - Full validation suite required to ensure no regressions

**Mitigation**: Use comprehensive backup strategy, staged deployment, and thorough testing before production changes.

## Test Plan

1. **Schema validation**: `python scripts/validate_clickhouse_schema.py`
2. **Bootstrap testing**: Fresh bootstrap + reapply without data loss
3. **Smoke testing**: `scripts/smoke_qtickets_dryrun.sh --env-file <path>`
4. **Unit testing**: `python -m pytest` under `dashboard-mvp/vk-python`
5. **Integration testing**: All view compilation and data flow validation
6. **CI validation**: GitHub Actions workflow with all stages

## Acceptance Criteria (DoD)

- [ ] Exactly one canonical CREATE TABLE definition per ClickHouse object
- [ ] `bootstrap_clickhouse.sh` succeeds twice consecutively (fresh + reapply)
- [ ] `scripts/smoke_qtickets_dryrun.sh` succeeds with exit code 0
- [ ] `python -m pytest` (vk-python) passes all tests
- [ ] `python scripts/validate_clickhouse_schema.py` reports success
- [ ] All views and materialized views compile without errors
- [ ] No residual TODOs or unaddressed duplicates remain
- [ ] Documentation updated (README, ADR, changelog, audit report)