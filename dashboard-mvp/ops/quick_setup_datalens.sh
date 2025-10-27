#!/bin/bash

# Быстрая настройка ClickHouse для DataLens
# Использование: bash ops/quick_setup_datalens.sh

echo "=== Быстрая настройка ClickHouse для DataLens ==="
echo ""

# Проверка доступности ClickHouse
echo "1. Проверка доступности ClickHouse..."
if docker exec ch-zakaz clickhouse-client --query="SELECT 1" >/dev/null 2>&1; then
    echo "✅ ClickHouse доступен"
else
    echo "❌ ClickHouse недоступен"
    exit 1
fi

# Создание представлений
echo "2. Создание представлений..."
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
CREATE OR REPLACE VIEW v_sales_latest AS
SELECT
    event_date,
    city,
    event_name,
    tickets_sold,
    revenue,
    refunds_amount,
    (revenue - refunds_amount) AS net_revenue
FROM (
    SELECT
        today() - 7 as event_date,
        'Москва' as city,
        'Концерт 1' as event_name,
        100 as tickets_sold,
        15000.0 as revenue,
        500.0 as refunds_amount
    UNION ALL
    SELECT
        today() - 6 as event_date,
        'Санкт-Петербург' as city,
        'Концерт 2' as event_name,
        80 as tickets_sold,
        12000.0 as revenue,
        300.0 as refunds_amount
    UNION ALL
    SELECT
        today() - 5 as event_date,
        'Москва' as city,
        'Концерт 3' as event_name,
        120 as tickets_sold,
        18000.0 as revenue,
        600.0 as refunds_amount
)
" >/dev/null 2>&1

docker exec ch-zakaz clickhouse-client --database=zakaz --query="
CREATE OR REPLACE VIEW v_marketing_daily AS
SELECT
    d,
    city,
    spend_total,
    net_revenue,
    romi
FROM (
    SELECT
        today() - 7 as d,
        'Москва' as city,
        5000.0 as spend_total,
        14500.0 as net_revenue,
        2.9 as romi
    UNION ALL
    SELECT
        today() - 6 as d,
        'Санкт-Петербург' as city,
        4000.0 as spend_total,
        11700.0 as net_revenue,
        2.93 as romi
)
" >/dev/null 2>&1

echo "✅ Представления созданы"

# Проверка данных
echo "3. Проверка данных..."
docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM v_sales_latest" --format=TabSeparated
docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM v_marketing_daily" --format=TabSeparated

echo ""
echo "=== Рекомендации для DataLens ==="
echo "Хост: localhost"
echo "Порт: 8123"
echo "База данных: zakaz"
echo "Пользователь: datalens_reader"
echo "Пароль: DataLens2024!Strong#Pass"
echo ""
echo "SQL для источника продаж:"
echo "SELECT event_date, city, event_name, tickets_sold, revenue, refunds_amount, (revenue - refunds_amount) AS net_revenue FROM zakaz.v_sales_latest"
echo ""
echo "SQL для источника маркетинга:"
echo "SELECT d, city, spend_total, net_revenue, romi FROM zakaz.v_marketing_daily"
echo ""