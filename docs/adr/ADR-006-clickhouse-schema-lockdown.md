# ADR-006: Full Schema & Integration Lockdown - Complete Schema Consistency
**Date:** 2025-10-28
**Status:** Accepted

## Context

Following Task 005 completion, additional schema inconsistencies were discovered during Task 006 execution. The repository still contained conflicting definitions for critical tables and dependency issues where views referenced non-existent tables, causing bootstrap failures.

Key issues identified:
1. **Table reference errors** - Views referenced tables that didn't exist (`fact_qtickets_inventory_latest` created after views)
2. **Schema inconsistencies** - Missing fields in canonical schemas across files
3. **Syntax errors** - Python compilation errors in build pipeline
4. **Bootstrap ordering** - Tables created after dependent views in bootstrap sequence

## Decision

We implemented complete schema lockdown by:

1. **Fixing table creation order** - Moved table definitions before dependent views in bootstrap sequences
2. **Resolving all schema conflicts** - Added missing fields (`_loaded_at`, `order_id`, `run_id`) across all files
3. **Enhanced validation** - Improved schema validation script to detect cross-file inconsistencies
4. **Fixed syntax errors** - Corrected Python compilation issues in pipeline code
5. **Comprehensive testing** - Verified bootstrap idempotency, smoke tests, and compilation

## Implementation Details

### Critical Fixes Applied

#### Bootstrap Creation Order Fixes
- **fact_qtickets_inventory_latest**: Moved definition before `v_qtickets_inventory` view (line 565)
- **dim_events**: Moved definition before `v_qtickets_freshness` view (line 630)
- Removed duplicate table definitions from bootstrap files

#### Schema Consistency Fixes
- **fact_qtickets_sales**: Added missing `_loaded_at DateTime DEFAULT now()` field
- **meta_job_runs**: Standardized on canonical schema with `run_id String` field
- **stg_qtickets_api_orders_raw**: Added missing `order_id String` field
- **stg_qtickets_sheets_inventory**: Added missing `_loaded_at DateTime DEFAULT now()` field

#### Reference Updates
- Updated all views to use `fact_qtickets_inventory_latest` instead of deprecated `fact_qtickets_inventory`
- Fixed grant permissions to reference correct table names
- Updated smoke check scripts to use correct table references

#### Python Compilation Fixes
- Fixed syntax error in `build_dm_sales_incr.py`: `today freshness_hours = 0` → `today_freshness_hours = 0`
- Fixed corrupted test file header in `test_transform.py`

### Validation Enhancements

Enhanced `validate_clickhouse_schema.py` with:
- Extended DDL_FILES list including all migration and init scripts
- New `check_schema_consistency()` function to detect cross-file schema conflicts
- Comprehensive reporting of table definition inconsistencies

## Test Results

| Test | Status | Details |
|------|--------|---------|
| **Schema Validation** | ✅ PASS | Enhanced validator reports "Schema validation passed." |
| **Fresh Bootstrap** | ✅ PASS | 25 tables/views created successfully |
| **Idempotent Bootstrap** | ✅ PASS | Second bootstrap runs without errors |
| **Smoke Tests (API)** | ✅ PASS | Exit code 0, dry-run successful |
| **Unit Tests** | ✅ PASS | 3/3 pytest tests passed |
| **Python Compilation** | ✅ PASS | All Python files compile successfully |
| **Table Structure Verification** | ✅ PASS | All canonical tables created with correct schema |

## Bootstrap Execution Results

### First Bootstrap
```
[bootstrap] ClickHouse is healthy.
[bootstrap] Applying bootstrap_schema.sql...
[bootstrap] Listing tables in zakaz...
25 tables created including:
- dim_events (canonical schema)
- fact_qtickets_inventory (canonical schema)
- fact_qtickets_inventory_latest (canonical schema)
- fact_qtickets_sales (canonical schema)
- meta_job_runs (canonical schema)
- All views and materialized views
```

### Second Bootstrap (Idempotency Test)
```
[bootstrap] ClickHouse is healthy.
[bootstrap] Applying bootstrap_schema.sql...
[bootstrap] Listing tables in zakaz...
Same 25 tables confirmed - no errors on re-application
```

### Canonical Table Structures Verified

**dim_events:**
```
event_id      String
event_name    String
city          LowCardinality(String)
start_date    Nullable(Date)
end_date      Nullable(Date)
tickets_total UInt32 DEFAULT 0
tickets_left  UInt32 DEFAULT 0
_ver          UInt64
_loaded_at    DateTime DEFAULT now()
```

**fact_qtickets_inventory_latest:**
```
snapshot_ts   DateTime
event_id      String
event_name    String
city          LowCardinality(String)
tickets_total Nullable(UInt32)
tickets_left  Nullable(UInt32)
_ver          UInt64
```

## Risks Mitigated

1. **Bootstrap failure prevention** - Fixed table creation order eliminating dependency errors
2. **Schema drift elimination** - Single canonical schema enforced across all files
3. **Deployment reliability** - Idempotent bootstrap prevents production deployment issues
4. **Data consistency** - All tables use consistent field naming and typing
5. **Build pipeline stability** - Python compilation errors resolved

## Future Considerations

1. **Automated dependency checking** - Consider adding dependency order validation to bootstrap script
2. **Schema evolution policy** - Established pattern for maintaining consistency during future changes
3. **Testing automation** - All validation steps now pass and can be integrated into CI/CD
4. **Documentation updates** - ADR provides architectural guidance for schema management

## Acceptance Criteria (DoD)

- [x] Exactly one canonical CREATE TABLE definition per ClickHouse object
- [x] `bootstrap_clickhouse.sh` succeeds twice consecutively (fresh + reapply)
- [x] `scripts/smoke_qtickets_dryrun.sh` succeeds with exit code 0
- [x] `python -m pytest` (vk-python) passes all tests
- [x] `python scripts/validate_clickhouse_schema.py` reports success
- [x] `python -m compileall dashboard-mvp` succeeds without syntax errors
- [x] All views and materialized views compile without errors
- [x] No residual conflicts or duplicate definitions remain
- [x] Documentation updated (this ADR, changelog, audit report)

## Impact

This lockdown ensures:
- **Reliable deployments** - Bootstrap process is now completely idempotent
- **Schema consistency** - Single source of truth enforced across all files
- **Operational safety** - No more schema conflicts or dependency errors
- **Development productivity** - Clear validation and testing pipeline
- **Production readiness** - All validation checks pass successfully

---

**Next Steps**: Repository is now production-ready with complete schema consistency and full validation suite.