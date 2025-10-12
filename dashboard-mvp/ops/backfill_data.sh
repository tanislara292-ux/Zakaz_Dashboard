#!/bin/bash

# Скрипт для выполнения backfill данных за 90 дней
# Использование: bash ops/backfill_data.sh

set -e

echo "=== Начало загрузки исторических данных за 90 дней ==="

# Проверка наличия необходимых файлов
if [ ! -f "secrets/.env.qtickets" ]; then
    echo "Ошибка: Файл secrets/.env.qtickets не найден"
    exit 1
fi

if [ ! -f "secrets/.env.vk_ads" ]; then
    echo "Ошибка: Файл secrets/.env.vk_ads не найден"
    exit 1
fi

if [ ! -f "secrets/.env.direct" ]; then
    echo "Ошибка: Файл secrets/.env.direct не найден"
    exit 1
fi

if [ ! -f "secrets/.env.ch" ]; then
    echo "Ошибка: Файл secrets/.env.ch не найден"
    exit 1
fi

# Проверка наличия токенов
if grep -q "TODO_GET_TOKEN" secrets/.env.vk_ads; then
    echo "Ошибка: Необходимо получить токен VK Ads"
    echo "Смотрите инструкцию в ops/TOKEN_GUIDE.md"
    exit 1
fi

if grep -q "TODO_GET_OAUTH_TOKEN" secrets/.env.direct; then
    echo "Ошибка: Необходимо получить токен Яндекс.Директ"
    echo "Смотрите инструкцию в ops/TOKEN_GUIDE.md"
    exit 1
fi

# Загрузка данных QTickets
echo "=== Загрузка данных QTickets за 90 дней ==="
python -m integrations.qtickets.loader --days 90 --verbose --envfile secrets/.env.qtickets --ch-env secrets/.env.ch

# Загрузка данных VK Ads
echo "=== Загрузка данных VK Ads за 90 дней ==="
python -m integrations.vk_ads.loader --days 90 --verbose --envfile secrets/.env.vk_ads --ch-env secrets/.env.ch

# Загрузка данных Яндекс.Директ
echo "=== Загрузка данных Яндекс.Директ за 90 дней ==="
python -m integrations.direct.loader --days 90 --verbose --envfile secrets/.env.direct --ch-env secrets/.env.ch

echo "=== Проверка загруженных данных ==="

# Проверка данных в ClickHouse
echo "Проверка наличия данных в ClickHouse..."

# Проверка продаж
SALES_COUNT=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT count() FROM zakaz.v_sales_latest WHERE event_date >= today()-7" 2>/dev/null || echo "0")
echo "Количество записей о продажах за последние 7 дней: $SALES_COUNT"

# Проверка маркетинговых данных
MARKETING_SPEND=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT sum(spend_total) FROM zakaz.v_marketing_daily WHERE d >= today()-7" 2>/dev/null || echo "0")
echo "Сумма расходов на маркетинг за последние 7 дней: $MARKETING_SPEND"

# Проверка максимальных дат
MAX_EVENT_DATE=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT max(event_date) FROM zakaz.v_sales_latest" 2>/dev/null || echo "NULL")
echo "Максимальная дата мероприятия: $MAX_EVENT_DATE"

MAX_MARKETING_DATE=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT max(d) FROM zakaz.v_marketing_daily" 2>/dev/null || echo "NULL")
echo "Максимальная дата маркетинговых данных: $MAX_MARKETING_DATE"

# Проверка метаданных о запусках
echo "=== Последние запуски загрузчиков ==="
docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT job, started_at, status, rows_written FROM zakaz.meta_job_runs ORDER BY started_at DESC LIMIT 10" 2>/dev/null || echo "Нет данных о запусках"

echo "=== Backfill данных завершен ==="
echo ""
echo "Далее выполните:"
echo "1. Настройте подключение DataLens к ClickHouse"
echo "2. Создайте дашборд в DataLens"
echo "3. Настройте systemd таймеры для автоматической загрузки"