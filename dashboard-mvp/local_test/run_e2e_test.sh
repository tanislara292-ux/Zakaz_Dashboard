#!/bin/bash
set -euo pipefail

# E2E Testing Script for QTickets API Integration
# This script sets up local environment and runs comprehensive tests

echo "🚀 Starting E2E Test for QTickets API Integration"

# Set up environment
export PYTHONPATH=$(pwd)
export CH_DATABASE=zakaz_test
export CH_HOST=localhost
export CH_PORT=8123
export CH_USER=admin
export CH_PASSWORD=admin_pass

# Create local test directories
mkdir -p local_test/ch/data
mkdir -p local_test/ch/logs
mkdir -p local_test/ch/config.d
mkdir -p local_test/ch/users.d

# Start ClickHouse
echo "📦 Starting ClickHouse..."
cd local_test/ch
docker compose up -d

# Wait for ClickHouse to be ready
echo "⏳ Waiting for ClickHouse to be ready..."
sleep 30

# Create test database
echo "🗄️ Creating test database..."
docker exec -it ch-zakaz clickhouse-client -q "CREATE DATABASE IF NOT EXISTS zakaz_test;"

# Apply migration
echo "🔧 Applying migration..."
docker exec -i ch-zakaz clickhouse-client < ../../infra/clickhouse/migrations/2025-qtickets-api.LOCAL.sql

# Run unit tests
echo "🧪 Running unit tests..."
cd ../..
python -m pytest integrations/qtickets_api/tests/ -v

# Run loader in offline mode
echo "🔄 Running loader in offline mode..."
python -m integrations.qtickets_api.loader \
  --envfile configs/.env.qtickets_api.sample \
  --offline-fixtures-dir integrations/qtickets_api/fixtures \
  --dry-run \
  --verbose

# Run smoke checks
echo "🔍 Running smoke checks..."
docker exec -i ch-zakaz clickhouse-client < ../../infra/clickhouse/smoke_checks_qtickets_api.LOCAL.sql

echo "✅ E2E Test completed successfully!"
echo "📊 Check the results above for any issues"

# Stop ClickHouse
echo "🛑 Stopping ClickHouse..."
cd local_test/ch
docker compose down

echo "🎉 All tests completed!"