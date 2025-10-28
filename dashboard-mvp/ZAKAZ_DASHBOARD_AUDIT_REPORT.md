
## 7. Task 007 - ClickHouse Schema Canonicalization & Test Evidence (2025-10-28)

**Objective:** Complete schema unification across all SQL sources with comprehensive evidence collection.

### Commands Executed:
1. **SQL File Inventory:**
   ```bash
   rg "CREATE TABLE IF NOT EXISTS zakaz\." -n -g "*.sql" dashboard-mvp/infra/clickhouse | tee logs/create_table_inventory.log
   ```

2. **Schema Canonicalization:**
   - Updated migrations/2025-qtickets-api.sql to match bootstrap_schema.sql canonical schemas
   - Added missing fact_qtickets_inventory table
   - Fixed all type inconsistencies (String → LowCardinality(String), UInt32 → Nullable(UInt32))
   - Updated VIEW dependencies to use correct field names
   - Added DROP TABLE statements for migration safety

3. **Enhanced Validator:**
   ```bash
   python scripts/validate_clickhouse_schema.py | tee logs/schema_validation_final.log
   ```

4. **Double Bootstrap Execution:**
   ```bash
   ./scripts/bootstrap_clickhouse.sh 2>&1 | tee logs/bootstrap_first.log
   ./scripts/bootstrap_clickhouse.sh 2>&1 | tee logs/bootstrap_second.log
   ```

5. **Table Structure Verification:**
   ```bash
   docker exec ch-zakaz clickhouse-client -q "DESCRIBE TABLE zakaz.dim_events FORMAT TabSeparatedWithNames" | tee logs/describe_dim_events.tsv
   docker exec ch-zakaz clickhouse-client -q "DESCRIBE TABLE zakaz.fact_qtickets_inventory FORMAT TabSeparatedWithNames" | tee logs/describe_fact_inv.tsv
   docker exec ch-zakaz clickhouse-client -q "DESCRIBE TABLE zakaz.fact_qtickets_inventory_latest FORMAT TabSeparatedWithNames" | tee logs/describe_fact_inv_latest.tsv
   ```

6. **Smoke Tests:**
   ```bash
   ./dashboard-mvp/scripts/smoke_qtickets_dryrun.sh 2>&1 | tee logs/smoke_qtickets.log
   ```

7. **Python Testing:**
   ```bash
   python scripts/validate_clickhouse_schema.py 2>&1 | tee logs/schema_validation.log
   python -m compileall dashboard-mvp 2>&1 | tee logs/compileall.log
   cd dashboard-mvp/vk-python && python -m pytest 2>&1 | tee ../../logs/pytest.log
   docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:test . 2>&1 | tee logs/docker_build.log
   ```

### Results:
- ✅ **Schema Validation**: All 8 SQL files have identical canonical schemas
- ✅ **Bootstrap Idempotency**: Both first and second bootstrap completed successfully (25 tables each)
- ✅ **Smoke Tests**: Qtickets API dry-run completed with exit code 0
- ✅ **Unit Tests**: 3/3 pytest tests passed
- ✅ **Python Compilation**: All files compile successfully
- ✅ **Docker Build**: Qtickets API image built successfully

### Evidence Files Created:
- `logs/create_table_inventory.log` - Complete SQL file inventory
- `logs/canonical_schemas.md` - Reference schema definitions
- `logs/bootstrap_first.log` - Fresh bootstrap execution
- `logs/bootstrap_second.log` - Idempotent bootstrap execution
- `logs/describe_dim_events.tsv` - dim_events table structure
- `logs/describe_fact_inv.tsv` - fact_qtickets_inventory table structure
- `logs/describe_fact_inv_latest.tsv` - fact_qtickets_inventory_latest table structure
- `logs/smoke_qtickets.log` - Smoke test execution
- `logs/schema_validation_*.log` - Various validation runs
- `logs/pytest.log` - Unit test results
- `logs/compileall.log` - Python compilation results
- `logs/docker_build.log` - Docker build results

### Files Modified:
- `dashboard-mvp/infra/clickhouse/migrations/2025-qtickets-api.sql` - Complete schema rewrite
- `scripts/validate_clickhouse_schema.py` - Enhanced with init_mail.sql coverage
- `docs/adr/ADR-007-clickhouse-schema-canonicalization.md` - Architecture decision
- `docs/changelog/CHANGELOG-007.md` - Comprehensive changelog

### Git Status:
- All changes committed to feature/task-007-schema-canonicalization branch
- Working tree clean
- Ready for merge to main


