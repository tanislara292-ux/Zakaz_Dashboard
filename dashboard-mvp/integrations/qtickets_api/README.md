# QTickets API Integration

Production-ready module for ingesting sales and inventory data from the official QTickets REST API into ClickHouse. Replaces the legacy Google Sheets flow (`integrations/qtickets_sheets`) and is scheduled to run every 15 minutes in production.

## Status: PRODUCTION READY ✅

- ✅ GET `/orders` endpoint confirmed working
- ✅ Personal data protection (GDPR compliant)
- ✅ Docker containerization
- ✅ systemd timer integration
- ✅ ClickHouse migrations ready

## Prerequisites

1. Request an organiser API token from the QTickets web console:  
   **Настройки → Основное → API → Сгенерировать токен.**
2. Copy the token to the production server and place it into `secrets/.env.qtickets_api` using the template below.
3. Ensure the ClickHouse writer credentials (`etl_writer`) are available in the same dotenv file or in `secrets/.env.ch`.

## Environment Variables

Create `configs/.env.qtickets_api.sample` (see template in this repository) and copy it to `secrets/.env.qtickets_api` on the server with production values.

Required keys:

```bash
# QTickets API configuration (updated variable names)
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
# Or for custom domain: QTICKETS_BASE_URL=https://irs-prod.qtickets.ru/api/rest/v1
QTICKETS_TOKEN=<organiser_bearer_token>

# ClickHouse configuration
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=<password>
CLICKHOUSE_DATABASE=zakaz

# System settings
TZ=Europe/Moscow
ORG_NAME=zakaz
```

**Note:** Old variable names (`QTICKETS_API_BASE_URL`, `QTICKETS_API_TOKEN`) are supported for backward compatibility.

## Manual Execution

### Local Development
```bash
python -m integrations.qtickets_api.loader \
  --envfile secrets/.env.qtickets_api \
  --since-hours 24 \
  --dry-run \
  --verbose
```

### Production Docker Run
```bash
docker run --rm \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24
```

Remove `--dry-run` to persist data into ClickHouse. Use `--since-hours` to expand the lookback window (default = 24 hours).

## Production Deployment

### Docker Container
The integration runs in Docker containers managed by systemd timers:

```bash
# Build the image
docker build -t qtickets_api:latest integrations/qtickets_api

# Run manually (for testing)
docker run --rm \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run
```

### systemd Timer
Production deployment uses systemd timer for scheduled execution:

```bash
# Enable timer
sudo systemctl enable --now qtickets_api.timer

# Check status
systemctl status qtickets_api.timer

# View logs
journalctl -u qtickets_api.service --no-pager --since "1 hour ago"
```

## Log Interpretation

- `[qtickets_api] Starting QTickets API ingestion run` — loader initialization
- `[qtickets_api] Fetching orders via GET` — API client uses GET method (production)
- `[qtickets_api] Transformed orders into sales rows` — data prepared for ClickHouse
- `[qtickets_api] Built inventory snapshot` — inventory aggregation completed
- `[qtickets_api] Dry-run summary` — summary in dry-run mode with counts
- `Temporary QTickets API error` — transient 429/5xx responses handled with retry

## Production Monitoring

### ClickHouse Data Verification
```sql
-- Check recent data freshness
SELECT count(), max(sale_ts) FROM zakaz.stg_qtickets_api_orders_raw 
WHERE sale_ts > now() - INTERVAL 1 DAY;

-- Check aggregated sales
SELECT sales_date, sum(tickets_sold), sum(revenue) 
FROM zakaz.fact_qtickets_sales_daily 
WHERE sales_date >= today() - 7 
GROUP BY sales_date ORDER BY sales_date DESC;

-- Check inventory
SELECT city, sum(tickets_left) 
FROM zakaz.fact_qtickets_inventory_latest 
GROUP BY city ORDER BY city;

-- Job runs monitoring
SELECT job, status, started_at, message 
FROM zakaz.meta_job_runs 
WHERE job = 'qtickets_api' 
ORDER BY started_at DESC LIMIT 10;
```

### Smoke Checks
Run production smoke checks:
```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<password>' \
  < infra/clickhouse/smoke_checks_qtickets_api.sql
```

### Health Monitoring
- Check job runs in `zakaz.meta_job_runs` table
- Monitor systemd logs: `journalctl -u qtickets_api.service -f`
- Verify DataLens connectivity: query as `datalens_reader` user
- Alert on: no data > 2 hours, >5% failed runs

## Security & Compliance

- **GDPR Compliant**: No personal data (email, phone, name) stored or logged
- **Secrets Management**: All tokens in `/opt/zakaz_dashboard/secrets/.env.qtickets_api`
- **Role Separation**: `etl_writer` for writes, `datalens_reader` for reads
- **Audit Trail**: All job runs logged in `meta_job_runs` table
