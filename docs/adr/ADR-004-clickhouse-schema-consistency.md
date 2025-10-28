# ADR-004: Consistent ClickHouse Schema for dim_events and Related Objects
**Date:** 2025-10-28
**Status:** Accepted

## Context

During Task 004 execution, we identified that ClickHouse DDL schemas contained multiple conflicting definitions for `zakaz.dim_events` and related tables across various SQL files. The main issues were:

1. **Multiple conflicting definitions** - `dim_events` was defined in 6+ different files with mixed old/new schema
2. **DROP TABLE statements in bootstrap** - Migration files with DROP statements were included in bootstrap scripts, preventing idempotent bootstrap
3. **Bootstrap failures** - Double bootstrap would fail because DROP statements would remove tables on second run
4. **Schema inconsistencies** - `fact_qtickets_inventory_latest` had different field types across files

## Decision

We decided to enforce a single authoritative schema by:

1. **Standardizing on new schema** - All `dim_events` definitions use `start_date`, `end_date`, `_loaded_at` fields (not `event_date`)
2. **Removing DROP statements** - All `DROP TABLE IF EXISTS` statements removed from bootstrap files to ensure idempotent operations
3. **Authoritative bootstrap sources** - `bootstrap_schema.sql` and `bootstrap_all.sql` serve as the single source of truth
4. **Keeping all CREATE statements** - Retained CREATE TABLE IF NOT EXISTS for all required tables but removed destructive DROP statements

## Consequences

### Positive
- **Idempotent bootstrap** - Double bootstrap now works successfully
- **Schema consistency** - All definitions use the same field names and types
- **No data loss** - Existing tables are preserved during subsequent bootstrap runs
- **Views compatibility** - All views correctly reference `start_date`/`end_date` fields

### Risks
- **Migration cleanup needed** - Migration files still contain DROP statements but are not used in regular bootstrap
- **Schema drift potential** - Future changes must be synchronized across all files
- **Testing required** - All changes validated through smoke tests and schema validation

## Implementation Details

### Files Modified
1. `/dashboard-mvp/infra/clickhouse/bootstrap_schema.sql` - Removed DROP statements
2. `/dashboard-mvp/infra/clickhouse/bootstrap_all.sql` - Removed DROP statements

### Schema Standardization
- `dim_events`: All definitions now use `(event_id, event_name, city, start_date, end_date, tickets_total, tickets_left, _ver, _loaded_at)`
- `fact_qtickets_inventory_latest`: Standardized on `LowCardinality(String)` for city and `Nullable(UInt32)` for tickets fields

### Testing
- ✅ Double bootstrap test passed (2 consecutive runs)
- ✅ Smoke SQL checks passed
- ✅ Schema validation passed
- ✅ Pytest tests passed (3/3)

## Monitoring

1. **Bootstrap verification** - Run `bootstrap_clickhouse.sh` twice after any schema changes
2. **Smoke checks** - Execute smoke SQL files after deployments
3. **Schema validation** - Run `validate_clickhouse_schema.py` to verify consistency

## Future Considerations

1. Consider extracting migration logic from bootstrap files entirely
2. Implement automated schema drift detection
3. Create migration versioning system to track schema changes
4. Consider using database migration tools like Flyway or Liquibase for better change management