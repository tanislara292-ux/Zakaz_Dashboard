#!/bin/bash

# Тестирование системы Zakaz Dashboard
# Использование: bash test_system.sh

echo "=== Тестирование системы Zakaz Dashboard ==="
echo "Дата: $(date)"
echo ""

# Переход в директорию проекта
if [ ! -f "integrations/qtickets/loader.py" ]; then
    cd ..
fi

# Создание директории для логов
mkdir -p logs/test

# Шаг 1: Проверка Docker
echo "1. Проверка Docker..."
if docker ps | grep -q "ch-zakaz"; then
    echo "✅ Docker контейнеры запущены"
else
    echo "❌ Контейнер ClickHouse не запущен"
    echo "Запустите: cd infra/clickhouse && docker-compose up -d"
    exit 1
fi

# Шаг 2: Проверка данных в ClickHouse
echo ""
echo "2. Проверка данных в ClickHouse..."

# Проверка таблицы QTickets
QTICKETS_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_qtickets_sales_raw" --format=TabSeparated 2>/dev/null || echo "0")
echo "   Таблица stg_qtickets_sales_raw: $QTICKETS_COUNT записей"

# Проверка представлений
SALES_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
MARKETING_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM v_marketing_daily" --format=TabSeparated 2>/dev/null || echo "0")
echo "   Представление v_sales_latest: $SALES_COUNT записей"
echo "   Представление v_marketing_daily: $MARKETING_COUNT записей"

# Шаг 3: Проверка доступа для DataLens
echo ""
echo "3. Проверка доступа для DataLens..."
READER_SALES=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
READER_MARKETING=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM v_marketing_daily" --format=TabSeparated 2>/dev/null || echo "0")

if [ "$READER_SALES" -gt 0 ] && [ "$READER_MARKETING" -gt 0 ]; then
    echo "✅ Пользователь datalens_reader имеет доступ к данным"
else
    echo "❌ Проблема с доступом для пользователя datalens_reader"
fi

# Шаг 4: Тестирование производительности
echo ""
echo "4. Тестирование производительности..."
start_time=$(date +%s)

# Тестовый запрос
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    event_date,
    city,
    SUM(tickets_sold) as tickets,
    SUM(revenue - refunds_amount) as revenue
FROM v_sales_latest
WHERE event_date >= today() - 7
GROUP BY event_date, city
ORDER BY revenue DESC
LIMIT 10
" --format=Null > logs/test/performance.log 2>&1

end_time=$(date +%s)
query_time=$((end_time - start_time))
echo "   Время выполнения запроса: ${query_time} секунд"

if [ "$query_time" -lt 5 ]; then
    echo "✅ Производительность запросов: ${query_time}с (< 5s)"
else
    echo "⚠️ Производительность запросов: ${query_time}s (> 5s)"
fi

# Шаг 5: Проверка качества данных
echo ""
echo "5. Проверка качества данных..."

# Проверка на дубликаты
DUPLICATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    count() - countDistinct(concat(event_date, city, event_name)) as duplicates
FROM v_sales_latest
WHERE event_date >= today() - 7
" --format=TabSeparated 2>/dev/null || echo "0")

# Проверка пропущенных дат
MISSING_DATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
WITH date_series AS (
    SELECT today() - number as date
    FROM numbers(7)
)
SELECT 
    COUNT(date_series.date) - COUNT(DISTINCT(event_date)) as missing_dates
FROM date_series
LEFT JOIN v_sales_latest ON date_series.date = event_date
WHERE date_series.date >= today() - 7
" --format=TabSeparated 2>/dev/null || echo "0")

echo "   Дубликаты: $DUPLICATES"
echo "   Пропущенные даты: $MISSING_DATES"

if [ "$DUPLICATES" -eq 0 ]; then
    echo "✅ Дубликаты отсутствуют"
else
    echo "⚠️ Обнаружены дубликаты: $DUPLICATES"
fi

if [ "$MISSING_DATES" -eq 0 ]; then
    echo "✅ Пропущенные даты отсутствуют"
else
    echo "⚠️ Пропущенные даты: $MISSING_DATES"
fi

# Шаг 6: Агрегированные метрики
echo ""
echo "6. Агрегированные метрики..."
SALES_SUM=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT sum(tickets_sold) FROM v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
REVENUE_SUM=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT sum(revenue - refunds_amount) FROM v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
echo "   Продано билетов: $SALES_SUM"
echo "   Общая выручка: $REVENUE_SUM"

# Шаг 7: Итоги
echo ""
echo "=== ИТОГИ ТЕСТИРОВАНИЯ ==="
TOTAL_RECORDS=$((QTICKETS_COUNT))

if [ "$QTICKETS_COUNT" -gt 0 ] && [ "$SALES_COUNT" -gt 0 ]; then
    STATUS="✅ УСПЕХ"
    EXIT_CODE=0
elif [ "$TOTAL_RECORDS" -gt 0 ]; then
    STATUS="⚠️ ЧАСТИЧНЫЙ УСПЕХ"
    EXIT_CODE=1
else
    STATUS="❌ НЕУДАЧА"
    EXIT_CODE=2
fi

echo "Статус: $STATUS"
echo "Всего записей: $TOTAL_RECORDS"
echo "QTickets: $QTICKETS_COUNT"
echo "Продажи: $SALES_COUNT записей"
echo "Маркетинг: $MARKETING_COUNT записей"
echo "Продано билетов: $SALES_SUM"
echo "Общая выручка: $REVENUE_SUM"
echo "Производительность: ${query_time}с"
echo "Качество данных: дубликаты=$DUPLICATES, пропущенные даты=$MISSING_DATES"
echo "DataLens доступ: продажи=$READER_SALES/$SALES_COUNT, маркетинг=$READER_MARKETING/$MARKETING_COUNT"

# Сохранение результатов
cat > logs/test/test_results_$(date +%Y%m%d_%H%M%S).txt << EOF
Тестирование системы Zakaz Dashboard - $(date)
======================================

Статус: $STATUS

Данные:
- Сырые записи (QTickets): $QTICKETS_COUNT
- Продажи: $SALES_COUNT
- Маркетинг: $MARKETING_COUNT
- Продано билетов: $SALES_SUM
- Общая выручка: $REVENUE_SUM

Производительность:
- Время запроса: ${query_time}с
- Статус: $(if [ $query_time -lt 5 ]; then echo "ХОРОШО (< 5s)"; else echo "МЕДЛЕННО (> 5s)"; fi)

Качество данных:
- Дубликаты: $DUPLICATES
- Пропущенные даты: $MISSING_DATES

DataLens:
- Продажи: $READER_SALES/$SALES_COUNT
- Маркетинг: $READER_MARKETING/$MARKETING_COUNT

Логи:
- Производительность: logs/test/performance.log
EOF

echo "✅ Отчет сохранен в logs/test/test_results_$(date +%Y%m%d_%H%M%S).txt"

exit $EXIT_CODE