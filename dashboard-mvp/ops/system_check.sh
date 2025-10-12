#!/bin/bash

# Скрипт для проверки работоспособности системы
# Использование: bash ops/system_check.sh

set -e

echo "=== Проверка системы Zakaz Dashboard ==="

# Проверка ClickHouse
echo "=== Проверка ClickHouse ==="
if docker exec ch-zakaz clickhouse-client -q "SELECT 1" >/dev/null 2>&1; then
    echo "✓ ClickHouse доступен"
    VERSION=$(docker exec ch-zakaz clickhouse-client -q "SELECT version()")
    echo "  Версия: $VERSION"
else
    echo "✗ ClickHouse недоступен"
    exit 1
fi

# Проверка HTTPS доступа
echo ""
echo "=== Проверка HTTPS доступа ==="
DOMAIN="bi.zakaz-dashboard.ru"
if curl -s -k https://$DOMAIN/ping >/dev/null 2>&1; then
    echo "✓ HTTPS доступен через $DOMAIN"
else
    echo "✗ HTTPS недоступен через $DOMAIN"
    echo "  Проверьте DNS A-запись и настройку Caddy"
fi

# Проверка healthcheck
echo ""
echo "=== Проверка healthcheck сервера ==="
if curl -s http://localhost:8080/healthz >/dev/null 2>&1; then
    echo "✓ Healthcheck сервер доступен"
    HEALTH_STATUS=$(curl -s http://localhost:8080/healthz | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
    echo "  Статус: $HEALTH_STATUS"
else
    echo "✗ Healthcheck сервер недоступен"
fi

# Проверка свежести данных
echo ""
echo "=== Проверка свежести данных ==="

# Проверка продаж
SALES_COUNT=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT count() FROM zakaz.v_sales_latest WHERE event_date >= today()-7" 2>/dev/null || echo "0")
echo "Записей о продажах за последние 7 дней: $SALES_COUNT"

if [ "$SALES_COUNT" -gt 0 ]; then
    echo "✓ Данные о продажах присутствуют"
else
    echo "✗ Отсутствуют данные о продажах за последние 7 дней"
fi

# Проверка маркетинговых данных
MARKETING_COUNT=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT count() FROM zakaz.v_marketing_daily WHERE d >= today()-7" 2>/dev/null || echo "0")
echo "Записей о маркетинговых данных за последние 7 дней: $MARKETING_COUNT"

if [ "$MARKETING_COUNT" -gt 0 ]; then
    echo "✓ Маркетинговые данные присутствуют"
else
    echo "✗ Отсутствуют маркетинговые данные за последние 7 дней"
fi

# Проверка статуса таймеров
echo ""
echo "=== Проверка статус таймеров ==="
systemctl list-timers | grep -E 'qtickets|vk_ads|direct|alerts|smoke_test_integrations' | while read line; do
    if echo "$line" | grep -q "NEXT"; then
        echo "✓ $line"
    else
        echo "? $line"
    fi
done

# Проверка последних запусков
echo ""
echo "=== Последние запуски загрузчиков ==="
docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "
SELECT 
    job,
    started_at,
    status,
    rows_written,
    err_msg
FROM zakaz.meta_job_runs 
ORDER BY started_at DESC 
LIMIT 10
FORMAT Vertical" 2>/dev/null || echo "Нет данных о запусках"

# Проверка алертов
echo ""
echo "=== Проверка алертов ==="
ALERTS_COUNT=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT count() FROM zakaz.alerts WHERE created_at >= today()-1" 2>/dev/null || echo "0")
echo "Алертов за последние 24 часа: $ALERTS_COUNT"

if [ "$ALERTS_COUNT" -eq 0 ]; then
    echo "✓ Алерты отсутствуют"
else
    echo "⚠ Есть алерты за последние 24 часа"
    docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "
    SELECT 
        alert_type,
        created_at,
        message
    FROM zakaz.alerts 
    WHERE created_at >= today()-1
    ORDER BY created_at DESC
    FORMAT Vertical" 2>/dev/null || echo "Нет данных об алертах"
fi

# Проверка бэкапов
echo ""
echo "=== Проверка бэкапов ==="
BACKUP_COUNT=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT count() FROM meta.backup_runs WHERE status = 'ok' AND ts >= now() - INTERVAL 1 DAY" 2>/dev/null || echo "0")
echo "Успешных бэкапов за последние 24 часа: $BACKUP_COUNT"

if [ "$BACKUP_COUNT" -gt 0 ]; then
    echo "✓ Бэкапы создаются"
    LAST_BACKUP=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "SELECT max(ts) FROM meta.backup_runs WHERE status = 'ok'" 2>/dev/null || echo "NULL")
    echo "  Последний бэкап: $LAST_BACKUP"
else
    echo "✗ Отсутствуют бэкапы за последние 24 часа"
fi

# Рекомендации
echo ""
echo "=== Рекомендации ==="

if [ "$SALES_COUNT" -eq 0 ]; then
    echo "- Выполните загрузку данных QTickets: bash ops/backfill_data.sh"
fi

if [ "$MARKETING_COUNT" -eq 0 ]; then
    echo "- Проверьте токены VK Ads и Яндекс.Директ в secrets/"
    echo "- Выполните загрузку маркетинговых данных"
fi

if [ "$ALERTS_COUNT" -gt 0 ]; then
    echo "- Проверьте логи таймеров: journalctl -u alerts.service -n 50"
fi

if [ "$BACKUP_COUNT" -eq 0 ]; then
    echo "- Настройте бэкапы: sudo bash ops/backup_full.sh"
fi

echo ""
echo "=== Проверка завершена ==="