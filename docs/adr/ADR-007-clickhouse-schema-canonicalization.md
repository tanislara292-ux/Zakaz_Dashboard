# ADR-007: ClickHouse Schema Canonicalization & Test Evidence
**Date:** 2025-10-28
**Status:** Accepted

## Context

Following the successful completion of Task 006 (Full Schema & Integration Lockdown), Task 007 was initiated to provide comprehensive evidence and further strengthen the schema canonicalization process. The task required ensuring that every SQL source in dashboard-mvp/infra/clickhouse/ creates identical ClickHouse schemas, that the validator catches any discrepancies, and that the complete bootstrap → smoke → tests → documentation cycle is executed and documented.

Key requirements identified:
1. Complete schema unification across all SQL files with identical table definitions
2. Enhanced validator covering all SQL files with consistency checking
3. Double bootstrap execution with full evidence collection
4. Comprehensive smoke testing and validation
5. Complete documentation and audit trail

## Decision

We implemented complete schema canonicalization with comprehensive evidence collection by:

1. **Full SQL File Inventory**: Identified all SQL files containing CREATE TABLE statements across the entire codebase
2. **Canonical Schema Enforcement**: Brought all table definitions to exact literal match with bootstrap_schema.sql canonical versions
3. **Enhanced Validator**: Extended the validation script to include all SQL files and robust cross-file consistency checking
4. **Evidence Collection**: Executed double bootstrap, smoke tests, and comprehensive validation with full log capture
5. **Complete Documentation**: Created ADR, changelog, and audit report with all evidence artifacts

## Implementation Details

### SQL Files Canonicalized
Total files processed: **8 SQL files**
- `bootstrap_schema.sql` (canonical source)
- `bootstrap_all.sql`
- `init.sql`
- `init_qtickets_sheets.sql`
- `init_integrations.sql`
- `init_mail.sql`
- `migrations/2025-qtickets-api.sql`
- `migrations/2025-qtickets-api-final.sql`

### Critical Schema Fixes Applied

#### Migration File 2025-qtickets-api.sql
**Problem**: Used outdated schema definitions inconsistent with canonical versions
**Solution**: Complete schema rewrite to match bootstrap_schema.sql:

1. **stg_qtickets_api_orders_raw**:
   - Added comprehensive comments
   - Added `SETTINGS index_granularity = 8192`
   - Enhanced PARTITION BY comment
   - Added DROP TABLE for migration safety

2. **stg_qtickets_api_inventory_raw**:
   - Updated city type: `String` → `LowCardinality(String)`
   - Added comprehensive comments
   - Added `_dedup_key` field for deduplication
   - Added SETTINGS and enhanced comments

3. **dim_events**:
   - Added comprehensive field comments
   - Added `SETTINGS index_granularity = 8192`
   - Enhanced PARTITION BY and ORDER BY comments
   - Added DROP TABLE for migration safety

4. **fact_qtickets_sales_daily**:
   - Field name: `date` → `sales_date` to match canonical
   - Removed non-canonical fields (event_name, refunds, currency, _loaded_at)
   - Updated to match exact canonical structure
   - Added DROP TABLE for migration safety

5. **fact_qtickets_inventory_latest**:
   - Updated city type: `String` → `LowCardinality(String)`
   - Updated ticket fields: `UInt32` → `Nullable(UInt32)`
   - Added comprehensive comments
   - Enhanced SETTINGS and comments

6. **fact_qtickets_inventory**:
   - Added missing table (was completely absent)
   - Created canonical schema matching bootstrap_schema.sql
   - Added comprehensive comments and settings

### VIEW Updates
All dependent views were updated to use correct field names:
- `v_sales_latest`: Updated to use `sales_date` instead of `date`
- `v_sales_14d`: Updated WHERE clause to use `sales_date`

### Enhanced Validator

Extended `scripts/validate_clickhouse_schema.py` with:

**New DDL_FILES Coverage:**
```python
DDL_FILES = [
    "bootstrap_schema.sql",
    "bootstrap_all.sql",
    "init.sql",
    "init_qtickets_sheets.sql",
    "init_integrations.sql",
    "init_mail.sql",                    # NEW
    "migrations/2025-qtickets-api.sql",
    "migrations/2025-qtickets-api-final.sql",
]
```

**Enhanced Consistency Checking:**
- Cross-file schema validation with column type and order checking
- Comprehensive error reporting showing all file differences
- Exit code 1 on schema conflicts
- Detailed conflict resolution guidance

### Test Results Evidence

| Test Category | Status | Evidence Location |
|---------------|--------|-------------------|
| **Schema Validation** | ✅ PASS | `logs/schema_validation_final.log` |
| **Fresh Bootstrap** | ✅ PASS | `logs/bootstrap_first.log` |
| **Idempotent Bootstrap** | ✅ PASS | `logs/bootstrap_second.log` |
| **Smoke Tests (API)** | ✅ PASS | `logs/smoke_qtickets.log` |
| **Unit Tests** | ✅ PASS (3/3) | `logs/pytest.log` |
| **Python Compilation** | ✅ PASS | `logs/compileall.log` |
| **Docker Build** | ✅ PASS | `logs/docker_build.log` |

### Bootstrap Execution Evidence

#### First Bootstrap Results
```
[bootstrap] ClickHouse is healthy.
[bootstrap] Applying bootstrap_schema.sql...
[bootstrap] Listing tables in zakaz...
25 tables created including:
- dim_events (canonical schema verified)
- fact_qtickets_inventory (canonical schema verified)
- fact_qtickets_inventory_latest (canonical schema verified)
- fact_qtickets_sales_daily (canonical schema verified)
- All staging and dimension tables
- All views and materialized views
```

#### Second Bootstrap Results (Idempotency Test)
```
[bootstrap] ClickHouse is healthy.
[bootstrap] Applying bootstrap_schema.sql...
[bootstrap] Listing tables in zakaz...
Same 25 tables confirmed - no errors on re-application
```

#### Canonical Table Structures Verified

**dim_events structure captured:**
```
name                type                        default_expression
event_id            String
event_name          String
city                LowCardinality(String)
start_date          Nullable(Date)
end_date            Nullable(Date)
tickets_total       UInt32       DEFAULT 0
tickets_left        UInt32       DEFAULT 0
_ver                UInt64
_loaded_at          DateTime     DEFAULT now()
```

**fact_qtickets_inventory_latest structure captured:**
```
name                type                        default_expression
snapshot_ts         DateTime
event_id            String
event_name          String
city                LowCardinality(String)
tickets_total       Nullable(UInt32)
tickets_left        Nullable(UInt32)
_ver                UInt64
```

### Smoke Test Results

**Qtickets API Smoke Test:**
- **Exit Code**: 0 ✅
- **Meta Job Runs**: Before: 0, After: 0 ✅ (no changes in DRY_RUN mode)
- **Docker Build**: Successful ✅
- **Stub Mode**: Confirmed working correctly ✅

### Validation Test Results

**Schema Validator Failure Test:**
- ✅ Successfully detected artificial schema inconsistency
- ✅ Provided detailed conflict reporting across files
- ✅ Returned exit code 1 on failure
- ✅ Passed again after fixing the inconsistency

## Risks Mitigated

1. **Schema Drift Prevention** - All SQL files now have identical table definitions
2. **Migration Safety** - DROP TABLE statements added to migration files
3. **Bootstrap Reliability** - Double bootstrap confirmed idempotent operation
4. **Validation Coverage** - All SQL files included in comprehensive validation
5. **Documentation Completeness** - Full evidence trail with all logs and artifacts

## Future Considerations

1. **Automated CI Integration** - All validation steps can be integrated into CI/CD pipeline
2. **Schema Evolution Policy** - Established patterns for maintaining consistency during future changes
3. **Validation Automation** - Enhanced validator provides immediate feedback on schema changes
4. **Evidence Collection** - Established pattern for comprehensive testing documentation

## Acceptance Criteria (DoD)

- [x] **Schema Unification**: All key tables have identical definitions across all SQL files
- [x] **Validator Coverage**: Script covers all SQL files and detects inconsistencies
- [x] **Bootstrap Success**: Both fresh and second bootstrap completed without errors
- [x] **Evidence Collection**: All logs and table structures captured and documented
- [x] **Smoke Tests**: Qtickets smoke test completed with exit code 0, meta_job_runs unchanged
- [x] **Test Suite**: Python compilation, pytest, and Docker build all successful
- [x] **Documentation**: ADR, changelog, and audit report updated with complete evidence
- [x] **Git Cleanliness**: Repository clean with only intended changes committed

## Impact

This canonicalization ensures:
- **Complete Schema Consistency** - Single source of truth enforced across all files
- **Robust Validation** - Automated detection of any schema discrepancies
- **Production Readiness** - All validation checks pass with comprehensive evidence
- **Development Safety** - Clear patterns and validation for future changes
- **Operational Reliability** - Idempotent bootstrap with full testing coverage

---

**Evidence Files Location:** `logs/` directory containing:
- `bootstrap_first.log` - Fresh bootstrap execution
- `bootstrap_second.log` - Idempotent bootstrap execution
- `describe_*.tsv` - Table structure verification files
- `smoke_qtickets.log` - Smoke test execution
- `schema_validation_*.log` - Validation results
- `pytest.log` - Unit test results
- `compileall.log` - Python compilation results
- `docker_build.log` - Docker build results
- `canonical_schemas.md` - Reference schema definitions
- `create_table_inventory.log` - Complete file inventory