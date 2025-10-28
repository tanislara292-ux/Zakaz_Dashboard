# CHANGELOG-005: ClickHouse Production Hardening

**Date:** 2025-10-28
**Task:** 005 - ClickHouse & Integrations Production Hardening
**Status:** ✅ COMPLETED

## Executive Summary

Successfully delivered production-hardened ClickHouse schema with single canonical definitions for all objects, resolved critical schema conflicts, and ensured full bootstrap/validation suite compatibility.

## 🔧 Critical Schema Fixes Applied

### 1. **stg_vk_ads_daily Schema Consolidation** (CRITICAL)
**Problem:** 3 conflicting schemas across 6+ files causing data inconsistency
**Solution:** Standardized on canonical CDC schema with proper typing
- **Before:** Mixed `UInt64` vs `String` campaign_id, `spent` vs `spend`, no versioning
- **After:** Consistent `String` campaign_id/ad_id, `Float64` spend, `_ver` versioning, monthly partitioning
- **Files Updated:** `bootstrap_all.sql`, `init.sql` (removed 2 duplicate definitions)

### 2. **fact_qtickets_inventory Table Creation** (HIGH)
**Problem:** Missing table referenced by multiple views causing failures
**Solution:** Created canonical fact table with proper schema
```sql
CREATE TABLE zakaz.fact_qtickets_inventory (
    event_id      String,
    city          LowCardinality(String),
    tickets_total UInt32 DEFAULT 0,
    tickets_left  UInt32 DEFAULT 0,
    _ver          UInt64,
    _loaded_at    DateTime DEFAULT now()
)
```

### 3. **Non-Deterministic Partitioning Fix** (MEDIUM)
**Problem:** `PARTITION BY toYYYYMM(today())` causing data inconsistencies
**Solution:** Replaced with deterministic `PARTITION BY tuple()` for inventory staging
- **File:** `init_qtickets_sheets.sql`

## 📊 Validation Results

| Test | Status | Details |
|------|--------|---------|
| **Schema Validation** | ✅ PASS | `python scripts/validate_clickhouse_schema.py` |
| **Unit Tests** | ✅ PASS | `python -m pytest` (3/3 tests) |
| **Fresh Bootstrap** | ✅ PASS | 41 tables/views created successfully |
| **Idempotent Bootstrap** | ✅ PASS | Second bootstrap runs without errors |
| **Smoke Checks (API)** | ✅ PASS | All SQL checks execute cleanly |
| **Smoke Checks (Sheets)** | ✅ PASS | All validation queries pass |

## 🏗️ Infrastructure Changes

### Bootstrap Improvements
- **Idempotency:** Bootstrap can now run multiple times safely
- **Canonical Sources:** Single source of truth for all object definitions
- **Table Created:** `fact_qtickets_inventory` now properly exists
- **Schema Consistency:** All `dim_events` definitions unified with `start_date`/`end_date`

### Schema Standardization
- **Versioning:** All tables use `_ver UInt64` for `ReplacingMergeTree`
- **Audit Fields:** `_loaded_at DateTime DEFAULT now()` standardized
- **Data Types:** `LowCardinality(String)` for string dimensions
- **Partitioning:** Deterministic column-based partitioning only

## 📁 Files Modified

### Core Schema Files
- `dashboard-mvp/infra/clickhouse/bootstrap_all.sql`
  - Updated `stg_vk_ads_daily` to canonical schema
  - Added `fact_qtickets_inventory` table definition
- `dashboard-mvp/infra/clickhouse/bootstrap_schema.sql`
  - Added `fact_qtickets_inventory` table definition
- `dashboard-mvp/infra/clickhouse/init.sql`
  - Removed 2 duplicate `stg_vk_ads_daily` definitions
- `dashboard-mvp/infra/clickhouse/init_qtickets_sheets.sql`
  - Fixed non-deterministic partitioning

### Documentation
- `docs/adr/ADR-005-clickhouse-production-hardening.md` (NEW)
- `docs/changelog/CHANGELOG-005.md` (NEW)
- `ZAKAZ_DASHBOARD_AUDIT_REPORT.md` (UPDATED)

## 🔍 Technical Debt Resolved

### Before Task 005
- ❌ Multiple conflicting `stg_vk_ads_daily` schemas
- ❌ Missing `fact_qtickets_inventory` table
- ❌ Non-deterministic partitioning clauses
- ❌ Bootstrap failures on second run
- ❌ Views referencing non-existent tables

### After Task 005
- ✅ Single canonical schema per object
- ✅ All required tables exist with proper structure
- ✅ Deterministic partitioning throughout
- ✅ Idempotent bootstrap process
- ✅ All views compile successfully

## 🚀 Production Readiness

### Definition of Done Met
- [x] Exactly one canonical CREATE TABLE definition per ClickHouse object
- [x] `bootstrap_clickhouse.sh` succeeds twice consecutively (fresh + reapply)
- [x] Smoke SQL checks pass with exit code 0
- [x] `python -m pytest` (vk-python) passes all tests
- [x] `python scripts/validate_clickhouse_schema.py` reports success
- [x] CI workflow covers all validation stages
- [x] Documentation updated (ADR, changelog, audit report)

### Risk Mitigation
- **Data Loss Prevention:** DROP statements removed from bootstrap
- **Schema Drift Detection:** Schema validation catches inconsistencies
- **Bootstrap Safety:** Idempotent process prevents corruption
- **Testing Coverage:** Full validation suite ensures reliability

## 📈 Impact Assessment

### Immediate Benefits
1. **Stable Deployments:** Bootstrap now works reliably in production
2. **Data Consistency:** Single schema eliminates conflicts
3. **Developer Experience:** Predictable environment setup
4. **Operational Safety:** Idempotent operations prevent accidents

### Future Considerations
1. **Schema Evolution:** Established pattern for future changes
2. **Monitoring:** Schema validation prevents regressions
3. **Documentation:** ADR provides architectural guidance
4. **CI Integration:** Automated validation ensures quality

## 🔗 References

- **ADR-005:** Production Hardening Architecture Decision
- **Task 004:** Previous schema consistency work
- **CI Pipeline:** Automated validation in `.github/workflows/ci.yml`
- **Bootstrap Script:** `scripts/bootstrap_clickhouse.sh`

---

**Next Steps:** Proceed with confidence to production deployment using hardened schema.