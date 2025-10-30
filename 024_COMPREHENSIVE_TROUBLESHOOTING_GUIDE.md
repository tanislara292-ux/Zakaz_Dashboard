# КОМПЛЕКСНОЕ РУКОВОДСТВО ПО РЕШЕНИЮ ПРОБЛЕМ И ПРОВЕРКАМ

## Обзор

Данное руководство содержит комплексные проверки, диагностику проблем и решения для всех компонентов системы Zakaz Dashboard. Включает проверочные скрипты, мониторинг и troubleshooting для production-среды.

---

## РАЗДЕЛ 1: СИСТЕМНЫЕ ПРОВЕРКИ

### 1.1 Ежедневная проверка работоспособности

```bash
#!/bin/bash
# daily_health_check.sh - Ежедневная проверка системы

echo "=== Ежедневная проверка Zakaz Dashboard ==="
echo "Дата: $(date +%Y-%m-%d %H:%M:%S)"
echo ""

# Проверка ClickHouse
echo "=== Проверка ClickHouse ==="
if docker exec ch-zakaz clickhouse-client -q "SELECT 1" >/dev/null 2>&1; then
    echo "✅ ClickHouse доступен"
    VERSION=$(docker exec ch-zakaz clickhouse-client -q "SELECT version()")
    echo "   Версия: $VERSION"
else
    echo "❌ ClickHouse недоступен"
    echo "   Действие: Перезапуск ClickHouse"
    cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
    docker-compose restart
fi

# Проверка HTTPS доступа
echo ""
echo "=== Проверка HTTPS доступа ==="
DOMAIN="bi.zakaz-dashboard.ru"
if curl -s -k https://$DOMAIN/?query=SELECT%201 >/dev/null 2>&1; then
    echo "✅ HTTPS доступен через $DOMAIN"
else
    echo "❌ HTTPS недоступен через $DOMAIN"
    echo "   Действие: Проверка Caddy и DNS"
    sudo systemctl status caddy
fi

# Проверка свежести данных
echo ""
echo "=== Проверка свежести данных ==="

# Проверка QTickets данных
QTICKETS_FRESHNESS=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password='ChangeMe123!' -q "
SELECT dateDiff('hour', max(sale_ts), now()) 
FROM zakaz.stg_qtickets_api_orders_raw" 2>/dev/null || echo "999")

if [ "$QTICKETS_FRESHNESS" -le 24 ]; then
    echo "✅ Данные QTickets свежие (${QTICKETS_FRESHNESS} часов)"
else
    echo "❌ Данные QTickets устарели (${QTICKETS_FRESHNESS} часов)"
    echo "   Действие: Проверка таймера qtickets_api"
    systemctl status qtickets_api.timer
fi

# Проверка маркетинговых данных
VK_FRESHNESS=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password='ChangeMe123!' -q "
SELECT dateDiff('hour', max(stat_date), now()) 
FROM zakaz.fact_vk_ads_daily" 2>/dev/null || echo "999")

if [ "$VK_FRESHNESS" -le 48 ]; then
    echo "✅ Данные VK Ads свежие (${VK_FRESHNESS} часов)"
else
    echo "❌ Данные VK Ads устарели (${VK_FRESHNESS} часов)"
    echo "   Действие: Проверка таймера vk_ads"
    systemctl status vk_ads.timer
fi

# Проверка статуса таймеров
echo ""
echo "=== Проверка статуса таймеров ==="
systemctl list-timers | grep -E 'qtickets|vk_ads|direct|alerts' | while read line; do
    if echo "$line" | grep -q "NEXT"; then
        echo "✅ $line"
    else
        echo "⚠️  $line"
    fi
done

# Проверка дискового пространства
echo ""
echo "=== Проверка дискового пространства ==="
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "✅ Дисковое пространство в норме (${DISK_USAGE}%)"
else
    echo "❌ Мало дискового пространства (${DISK_USAGE}%)"
    echo "   Действие: Очистка логов и старых бэкапов"
    docker system prune -f
    find /opt/zakaz_dashboard/logs -name "*.log" -mtime +7 -delete
fi

echo ""
echo "=== Проверка завершена ==="
```

### 1.2 Еженедельная глубокая проверка

```bash
#!/bin/bash
# weekly_deep_check.sh - Еженедельная глубокая проверка

echo "=== Еженедельная глубокая проверка ==="
echo "Дата: $(date +%Y-%m-%d)"
echo ""

# Проверка целостности данных
echo "=== Проверка целостности данных ==="
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
SELECT 
    'Data Integrity Check' as check_type,
    table_name,
    expected_rows,
    actual_rows,
    round(actual_rows * 100.0 / expected_rows, 2) as completeness_pct
FROM (
    SELECT 
        'stg_qtickets_api_orders_raw' as table_name,
        count() as actual_rows,
        1000 as expected_rows  -- Минимум 1000 строк за неделю
    FROM zakaz.stg_qtickets_api_orders_raw 
    WHERE sale_ts >= today() - INTERVAL 7 DAY
    
    UNION ALL
    
    SELECT 
        'fact_vk_ads_daily' as table_name,
        count() as actual_rows,
        7 as expected_rows  -- Минимум 7 дней данных
    FROM zakaz.fact_vk_ads_daily 
    WHERE stat_date >= today() - INTERVAL 7 DAY
    
    UNION ALL
    
    SELECT 
        'meta_job_runs' as table_name,
        count() as actual_rows,
        100 as expected_rows  -- Минимум 100 запусков за неделю
    FROM zakaz.meta_job_runs 
    WHERE started_at >= today() - INTERVAL 7 DAY
)
ORDER BY table_name"

# Проверка производительности запросов
echo ""
echo "=== Проверка производительности запросов ==="
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
SELECT 
    'Performance Check' as check_type,
    query_type,
    avg_execution_time,
    max_execution_time,
    query_count
FROM (
    SELECT 
        'DataLens Queries' as query_type,
        round(avg(execution_time), 3) as avg_execution_time,
        round(max(execution_time), 3) as max_execution_time,
        count() as query_count
    FROM system.query_log 
    WHERE user = 'datalens_reader' 
      AND event_date >= today() - INTERVAL 1 DAY
      AND exception = ''
    
    UNION ALL
    
    SELECT 
        'ETL Queries' as query_type,
        round(avg(execution_time), 3) as avg_execution_time,
        round(max(execution_time), 3) as max_execution_time,
        count() as query_count
    FROM system.query_log 
    WHERE user = 'etl_writer' 
      AND event_date >= today() - INTERVAL 1 DAY
      AND exception = ''
)
ORDER BY avg_execution_time DESC"

# Проверка ошибок
echo ""
echo "=== Проверка ошибок ==="
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
SELECT 
    'Error Check' as check_type,
    error_source,
    error_count,
    last_error_time,
    last_error_message
FROM (
    SELECT 
        'Job Runs' as error_source,
        count() as error_count,
        max(started_at) as last_error_time,
        any(message) as last_error_message
    FROM zakaz.meta_job_runs 
    WHERE status = 'error' 
      AND started_at >= today() - INTERVAL 7 DAY
    
    UNION ALL
    
    SELECT 
        'System Queries' as error_source,
        count() as error_count,
        max(event_time) as last_error_time,
        any(exception) as last_error_message
    FROM system.query_log 
    WHERE exception != '' 
      AND event_date >= today() - INTERVAL 1 DAY
)
HAVING error_count > 0
ORDER BY error_count DESC"

echo ""
echo "=== Еженедельная проверка завершена ==="
```

---

## РАЗДЕЛ 2: TROUBLESHOOTING ПО КОМПОНЕНТАМ

### 2.1 Проблемы с ClickHouse

#### Проблема: ClickHouse не запускается

**Симптомы**:
- Контейнер не запускается
- Ошибки в логах
- Нет ответа на запросы

**Диагностика**:
```bash
# Проверка статуса контейнера
docker ps -a | grep ch-zakaz

# Проверка логов
docker logs ch-zakaz --tail 100

# Проверка конфигурации
docker exec ch-zakaz cat /etc/clickhouse-server/config.xml
```

**Решения**:

1. **Проблема с правами доступа**:
```bash
# Исправление прав
sudo chown -R 101:101 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/data
sudo chown -R 101:101 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/logs
```

2. **Проблема с памятью**:
```bash
# Проверка доступной памяти
free -h

# Увеличение лимита памяти в docker-compose.yml
services:
  clickhouse:
    environment:
      - CLICKHOUSE_MAX_MEMORY_USAGE=8000000000
```

3. **Проблема с конфигурацией**:
```bash
# Проверка синтаксиса XML
xmllint --noout dashboard-mvp/infra/clickhouse/users.d/00-admin.xml
xmllint --noout dashboard-mvp/infra/clickhouse/users.d/10-service-users.xml
```

#### Проблема: Медленные запросы

**Диагностика**:
```bash
# Поиск медленных запросов
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
SELECT 
    query,
    execution_time,
    read_rows,
    result_rows,
    memory_usage
FROM system.query_log 
WHERE event_date >= today() - INTERVAL 1 DAY
  AND execution_time > 5
ORDER BY execution_time DESC 
LIMIT 10"

# Проверка использования ресурсов
docker stats ch-zakaz --no-stream
```

**Решения**:

1. **Оптимизация запросов**:
```sql
-- Используйте LIMIT для больших таблиц
SELECT * FROM zakaz.stg_qtickets_api_orders_raw 
WHERE sale_ts >= today() - INTERVAL 30 DAY 
LIMIT 10000

-- Используйте конкретные поля вместо SELECT *
SELECT event_id, city, revenue 
FROM zakaz.stg_qtickets_api_orders_raw 
WHERE sale_ts >= today() - INTERVAL 7 DAY
```

2. **Настройка индексов**:
```sql
-- Проверка наличия индексов
SELECT 
    table,
    name,
    type,
    expr
FROM system.data_skipping_indices 
WHERE database = 'zakaz'
```

### 2.2 Проблемы с QTickets API

#### Проблема: QTickets API не загружает данные

**Диагностика**:
```bash
# Проверка токена
curl -H "Authorization: Bearer ВАШ_ТОКЕН" \
     -H "Accept: application/json" \
     "https://qtickets.ru/api/rest/v1/orders?limit=1"

# Проверка логов сервиса
journalctl -u qtickets_api.service --since "1 hour ago" -n 50

# Ручной запуск для отладки
docker run --rm \
  --name qtickets_debug \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run --log-level DEBUG
```

**Решения**:

1. **Недействительный токен**:
```bash
# Обновление токена
nano /opt/zakaz_dashboard/secrets/.env.qtickets_api
# Изменить QTICKETS_TOKEN

# Перезапуск сервиса
sudo systemctl restart qtickets_api.service
```

2. **Проблемы с сетью**:
```bash
# Проверка доступности API
ping qtickets.ru
nslookup qtickets.ru

# Проверка HTTPS
curl -I https://qtickets.ru/api/rest/v1/orders
```

3. **Проблемы с форматом данных**:
```bash
# Проверка ответа API
curl -H "Authorization: Bearer ВАШ_ТОКЕН" \
     "https://qtickets.ru/api/rest/v1/orders?limit=5" | jq .
```

#### Проблема: Дубликаты данных

**Диагностика**:
```bash
# Проверка дубликатов
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
SELECT 
    order_id,
    count() as duplicate_count
FROM zakaz.stg_qtickets_api_orders_raw 
WHERE sale_ts >= today() - INTERVAL 1 DAY
GROUP BY order_id 
HAVING count() > 1 
ORDER BY duplicate_count DESC 
LIMIT 10"
```

**Решения**:
```bash
# Очистка дубликатов
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
ALTER TABLE zakaz.stg_qtickets_api_orders_raw 
DELETE WHERE _ver NOT IN (
    SELECT max(_ver) 
    FROM zakaz.stg_qtickets_api_orders_raw 
    GROUP BY _dedup_key
)"
```

### 2.3 Проблемы с VK Ads и Яндекс.Директ

#### Проблема: Не загружаются маркетинговые данные

**Диагностика**:
```bash
# Проверка токена VK
curl -H "Authorization: Bearer ВАШ_VK_ТОКЕН" \
     "https://api.vk.com/method/ads.getAccounts?v=5.131"

# Проверка токена Яндекс.Директ
curl -H "Authorization: Bearer ВАШ_ЯНДЕКС_ТОКЕН" \
     "https://api.direct.yandex.com/json/v5/campaigns"

# Проверка логов
journalctl -u vk_ads.service --since "1 hour ago" -n 20
journalctl -u direct.service --since "1 hour ago" -n 20
```

**Решения**:

1. **Истекший токен**:
```bash
# Обновление токенов
nano /opt/zakaz_dashboard/secrets/.env.vk
nano /opt/zakaz_dashboard/secrets/.env.direct

# Перезапуск сервисов
sudo systemctl restart vk_ads.service direct.service
```

2. **Проблемы с API лимитами**:
```bash
# Проверка лимитов в логах
journalctl -u vk_ads.service | grep -i "limit\|quota\|rate"

# Увеличение интервала между запросами
# В коде загрузчика добавить задержку
time.sleep(1)  # 1 секунда между запросами
```

### 2.4 Проблемы с DataLens

#### Проблема: DataLens не подключается к ClickHouse

**Диагностика**:
```bash
# Проверка HTTPS доступа
curl -k -u "datalens_reader:ChangeMe123!" \
     "https://bi.zakaz-dashboard.ru/?query=SELECT%201"

# Проверка прав пользователя
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
SHOW GRANTS FOR datalens_reader"

# Проверка сетевого доступа
telnet bi.zakaz-dashboard.ru 443
```

**Решения**:

1. **Неверные учетные данные**:
```bash
# Сброс пароля пользователя
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
ALTER USER datalens_reader IDENTIFIED BY 'ChangeMe123!'"

# Предоставление прав
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
GRANT SELECT ON zakaz.* TO datalens_reader;
GRANT SELECT ON system.tables TO datalens_reader;
GRANT SELECT ON system.databases TO datalens_reader"
```

2. **Проблемы с SSL сертификатом**:
```bash
# Проверка сертификата
openssl s_client -connect bi.zakaz-dashboard.ru:443 -servername bi.zakaz-dashboard.ru

# Перезапуск Caddy
sudo systemctl restart caddy
```

#### Проблема: Дашборды загружаются медленно

**Диагностика**:
```bash
# Анализ медленных запросов DataLens
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
SELECT 
    query,
    execution_time,
    read_rows,
    result_rows,
    memory_usage
FROM system.query_log 
WHERE user = 'datalens_reader' 
  AND event_date >= today() - INTERVAL 1 DAY
  AND execution_time > 3
ORDER BY execution_time DESC 
LIMIT 10"
```

**Решения**:

1. **Оптимизация SQL-запросов**:
```sql
-- Добавление ограничений по времени
WHERE event_date >= today() - INTERVAL 90 DAY

-- Использование предагрегированных данных
SELECT * FROM zakaz.v_qtickets_sales_14d  -- Вместо сырых данных
```

2. **Настройка кэширования**:
```bash
# В DataLens настройте кэширование датасетов
# Интервал: 15 минут
# Предзагрузка: включить
```

---

## РАЗДЕЛ 3: МОНИТОРИГ И АЛЕРТЫ

### 3.1 Настройка мониторинга

```bash
#!/bin/bash
# setup_monitoring.sh - Настройка мониторинга

# Создание скрипта мониторинга
cat > /opt/zakaz_dashboard/ops/monitoring.sh << 'EOF'
#!/bin/bash
# Скрипт мониторинга системы

ALERT_EMAIL="ads-irsshow@yandex.ru"
LOG_FILE="/opt/zakaz_dashboard/logs/monitoring.log"

# Функция отправки алерта
send_alert() {
    local subject=$1
    local message=$2
    echo "$(date): $subject - $message" >> $LOG_FILE
    echo "$message" | mail -s "$subject" $ALERT_EMAIL
}

# Проверка ClickHouse
if ! docker exec ch-zakaz clickhouse-client -q "SELECT 1" >/dev/null 2>&1; then
    send_alert "CRITICAL: ClickHouse недоступен" "Сервер ClickHouse не отвечает на запросы"
fi

# Проверка свежести данных
QTICKETS_HOURS=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password='ChangeMe123!' -q "
SELECT dateDiff('hour', max(sale_ts), now()) FROM zakaz.stg_qtickets_api_orders_raw" 2>/dev/null || echo "999")

if [ "$QTICKETS_HOURS" -gt 24 ]; then
    send_alert "WARNING: Данные QTickets устарели" "Данные не обновлялись ${QTICKETS_HOURS} часов"
fi

# Проверка дискового пространства
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 85 ]; then
    send_alert "WARNING: Место на диске заканчивается" "Использовано ${DISK_USAGE}% дискового пространства"
fi
EOF

chmod +x /opt/zakaz_dashboard/ops/monitoring.sh

# Добавление в cron для каждых 5 минут
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/zakaz_dashboard/ops/monitoring.sh") | crontab -
```

### 3.2 Настройка алертов в ClickHouse

```sql
-- Создание таблицы алертов
CREATE TABLE IF NOT EXISTS zakaz.alerts (
    alert_id UUID DEFAULT generateUUIDv4(),
    created_at DateTime DEFAULT now(),
    alert_type LowCardinality(String),
    severity LowCardinality(String),
    source LowCardinality(String),
    message String,
    details String,
    acknowledged Bool DEFAULT false
) ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at, alert_id);

-- Создание материализованного представления для алертов свежести данных
CREATE MATERIALIZED VIEW IF NOT EXISTS zakaz.mv_freshness_alerts
TO zakaz.alerts
AS SELECT
    generateUUIDv4() as alert_id,
    now() as created_at,
    'data_freshness' as alert_type,
    multiIf(
        hours_behind > 48, 'critical',
        hours_behind > 24, 'warning',
        'info'
    ) as severity,
    source as source,
    concat('Данные от источника ', source, ' устарели на ', toString(hours_behind), ' часов') as message,
    toString(hours_behind) as details,
    false as acknowledged
FROM (
    SELECT 
        'qtickets_api' as source,
        dateDiff('hour', max(sale_ts), now()) as hours_behind
    FROM zakaz.stg_qtickets_api_orders_raw
    
    UNION ALL
    
    SELECT 
        'vk_ads' as source,
        dateDiff('hour', max(stat_date), now()) as hours_behind
    FROM zakaz.fact_vk_ads_daily
)
WHERE hours_behind > 12;
```

---

## РАЗДЕЛ 4: АВТОМАТИЗАЦИЯ ВОССТАНОВЛЕНИЯ

### 4.1 Автоматическое восстановление ClickHouse

```bash
#!/bin/bash
# auto_recovery_clickhouse.sh - Автоматическое восстановление ClickHouse

CLICKHOUSE_CONTAINER="ch-zakaz"
MAX_RESTART_ATTEMPTS=3
RESTART_DELAY=30

check_clickhouse() {
    docker exec $CLICKHOUSE_CONTAINER clickhouse-client -q "SELECT 1" >/dev/null 2>&1
}

restart_clickhouse() {
    echo "Попытка перезапуска ClickHouse..."
    cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
    docker-compose restart
    sleep $RESTART_DELAY
}

# Основная логика восстановления
if ! check_clickhouse; then
    echo "ClickHouse недоступен, начинаем восстановление..."
    
    for attempt in $(seq 1 $MAX_RESTART_ATTEMPTS); do
        echo "Попытка $attempt из $MAX_RESTART_ATTEMPTS"
        restart_clickhouse
        
        if check_clickhouse; then
            echo "ClickHouse восстановлен после попытки $attempt"
            # Отправка уведомления
            echo "ClickHouse восстановлен успешно" | \
                mail -s "RECOVERY: ClickHouse восстановлен" ads-irsshow@yandex.ru
            exit 0
        fi
    done
    
    echo "Не удалось восстановить ClickHouse после $MAX_RESTART_ATTEMPTS попыток"
    # Отправка критического алерта
    echo "КРИТИЧЕСКАЯ ОШИБКА: ClickHouse не восстанавливается" | \
        mail -s "CRITICAL: ClickHouse недоступен" ads-irsshow@yandex.ru
    exit 1
fi
```

### 4.2 Автоматическая очистка ресурсов

```bash
#!/bin/bash
# auto_cleanup.sh - Автоматическая очистка ресурсов

# Очистка старых логов
find /opt/zakaz_dashboard/logs -name "*.log" -mtime +7 -delete
find /opt/zakaz_dashboard/logs -name "*.log.*" -mtime +7 -delete

# Очистка Docker ресурсов
docker system prune -f --volumes
docker image prune -f

# Очистка старых бэкапов (оставляем последние 10)
find /opt/zakaz_dashboard/backups -name "zakaz_backup_*" -type d | \
    sort -r | tail -n +11 | xargs rm -rf

# Очистка старых данных в ClickHouse
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
ALTER TABLE zakaz.stg_qtickets_api_orders_raw 
DELETE WHERE sale_ts < today() - INTERVAL 90 DAY"

echo "Очистка ресурсов завершена: $(date)"
```

---

## РАЗДЕЛ 5: ПРОВЕРОЧНЫЕ ЧЕК-ЛИСТЫ

### 5.1 Чек-лист перед передачей заказчику

```bash
#!/bin/bash
# pre_delivery_checklist.sh - Финальная проверка перед передачей

echo "=== ФИНАЛЬНАЯ ПРОВЕРКА ПЕРЕД ПЕРЕДАЧЕЙ ЗАКАЗЧИКУ ==="
CHECKLIST_FILE="/opt/zakaz_dashboard/pre_delivery_checklist.txt"

# Инициализация чек-листа
cat > $CHECKLIST_FILE << 'EOF'
ФИНАЛЬНЫЙ ЧЕК-ЛИСТ ПЕРЕД ПЕРЕДАЧЕЙ ЗАКАЗЧИКУ
Дата: $(date +%Y-%m-%d)

ИНФРАСТРУКТУРА:
EOF

# Проверка инфраструктуры
echo "Проверка инфраструктуры..." | tee -a $CHECKLIST_FILE

# Проверка ClickHouse
if docker exec ch-zakaz clickhouse-client -q "SELECT 1" >/dev/null 2>&1; then
    echo "✅ ClickHouse работает" | tee -a $CHECKLIST_FILE
else
    echo "❌ ClickHouse не работает" | tee -a $CHECKLIST_FILE
fi

# Проверка HTTPS
if curl -s -k https://bi.zakaz-dashboard.ru/?query=SELECT%201 >/dev/null 2>&1; then
    echo "✅ HTTPS доступ работает" | tee -a $CHECKLIST_FILE
else
    echo "❌ HTTPS доступ не работает" | tee -a $CHECKLIST_FILE
fi

# Проверка таймеров
echo "" | tee -a $CHECKLIST_FILE
echo "Проверка таймеров..." | tee -a $CHECKLIST_FILE
systemctl list-timers | grep -E 'qtickets|vk_ads|direct|alerts' | while read line; do
    if echo "$line" | grep -q "NEXT"; then
        echo "✅ $line" | tee -a $CHECKLIST_FILE
    else
        echo "❌ $line" | tee -a $CHECKLIST_FILE
    fi
done

# Проверка данных
echo "" | tee -a $CHECKLIST_FILE
echo "Проверка данных..." | tee -a $CHECKLIST_FILE

# Проверка наличия данных
QTICKETS_ROWS=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password='ChangeMe123!' -q "
SELECT count() FROM zakaz.stg_qtickets_api_orders_raw WHERE sale_ts >= today() - INTERVAL 7 DAY" 2>/dev/null || echo "0")

if [ "$QTICKETS_ROWS" -gt 0 ]; then
    echo "✅ Данные QTickets присутствуют (${QTICKETS_ROWS} строк)" | tee -a $CHECKLIST_FILE
else
    echo "❌ Отсутствуют данные QTickets" | tee -a $CHECKLIST_FILE
fi

# Проверка свежести
QTICKETS_FRESH=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password='ChangeMe123!' -q "
SELECT dateDiff('hour', max(sale_ts), now()) FROM zakaz.stg_qtickets_api_orders_raw" 2>/dev/null || echo "999")

if [ "$QTICKETS_FRESH" -le 24 ]; then
    echo "✅ Данные QTickets свежие (${QTICKETS_FRESH} часов)" | tee -a $CHECKLIST_FILE
else
    echo "❌ Данные QTickets устарели (${QTICKETS_FRESH} часов)" | tee -a $CHECKLIST_FILE
fi

# Проверка DataLens доступа
echo "" | tee -a $CHECKLIST_FILE
echo "Проверка доступа DataLens..." | tee -a $CHECKLIST_FILE

if curl -s -u "datalens_reader:ChangeMe123!" \
     "https://bi.zakaz-dashboard.ru/?query=SELECT%20count()%20FROM%20zakaz.v_qtickets_sales_latest" >/dev/null 2>&1; then
    echo "✅ DataLens доступ работает" | tee -a $CHECKLIST_FILE
else
    echo "❌ DataLens доступ не работает" | tee -a $CHECKLIST_FILE
fi

# Проверка безопасности
echo "" | tee -a $CHECKLIST_FILE
echo "Проверка безопасности..." | tee -a $CHECKLIST_FILE

# Проверка паролей по умолчанию
if grep -q "admin_pass\|ChangeMe123\|EtL2024" /opt/zakaz_dashboard/secrets/.env* 2>/dev/null; then
    echo "❌ Обнаружены пароли по умолчанию" | tee -a $CHECKLIST_FILE
else
    echo "✅ Пароли изменены" | tee -a $CHECKLIST_FILE
fi

# Проверка прав доступа к секретам
SECRET_PERMS=$(stat -c "%a" /opt/zakaz_dashboard/secrets)
if [ "$SECRET_PERMS" = "700" ]; then
    echo "✅ Права доступа к секретам корректны" | tee -a $CHECKLIST_FILE
else
    echo "❌ Некорректные права доступа к секретам (${SECRET_PERMS})" | tee -a $CHECKLIST_FILE
fi

echo "" | tee -a $CHECKLIST_FILE
echo "=== ПРОВЕРКА ЗАВЕРШЕНА ===" | tee -a $CHECKLIST_FILE
echo "Результаты сохранены в: $CHECKLIST_FILE"
```

### 5.2 Чек-лист для регулярного обслуживания

```bash
#!/bin/bash
# maintenance_checklist.sh - Чек-лист регулярного обслуживания

echo "=== ЧЕК-ЛИСТ РЕГУЛЯРНОГО ОБСЛУЖИВАНИЯ ==="
echo "Дата: $(date +%Y-%m-%d)"
echo ""

# Еженедельные задачи
echo "Еженедельные задачи:"
echo "□ Проверка обновлений системы"
echo "□ Очистка логов старше 7 дней"
echo "□ Проверка использования диска"
echo "□ Тестирование бэкапов"
echo "□ Проверка производительности запросов"
echo ""

# Ежемесячные задачи
echo "Ежемесячные задачи:"
echo "□ Обновление Docker образов"
echo "□ Проверка и обновление SSL сертификатов"
echo "□ Анализ трендов использования ресурсов"
echo "□ Обзор и обновление документации"
echo "□ Проверка алертов и их настройка"
echo ""

# Квартальные задачи
echo "Квартальные задачи:"
echo "□ Полный аудит безопасности"
echo "□ Тестирование аварийного восстановления"
echo "□ Оптимизация производительности"
echo "□ Обзор и планирование емкости"
echo "□ Обучение пользователей новым функциям"
echo ""

# Команды для выполнения
echo "Команды для выполнения:"
echo "# Проверка обновлений:"
echo "sudo apt update && sudo apt list --upgradable"
echo ""
echo "# Очистка Docker:"
echo "docker system prune -f"
echo ""
echo "# Проверка бэкапов:"
echo "ls -la /opt/zakaz_dashboard/backups/"
echo ""
echo "# Анализ логов ошибок:"
echo "journalctl -u qtickets_api.service --since '7 days ago' | grep -i error"
```

---

## РАЗДЕЛ 6: КОНТАКТЫ И ЭСКАЛАЦИЯ

### 6.1 Уровни поддержки

| Уровень | Проблема | Контакты | Время реакции |
|---------|-----------|-----------|--------------|
| **Level 1** | Базовые вопросы, инструкции | Документация, внутренняя база знаний | 4 часа |
| **Level 2** | Технические проблемы, ошибки | Техническая поддержка: [контакт] | 2 часа |
| **Level 3** | Критические сбои, недоступность | Экстренный контакт: [контакт] | 30 минут |

### 6.2 Шаблон сообщения о проблеме

```
Тема: [КРИТИЧНОСТЬ] Краткое описание проблемы

Система: Zakaz Dashboard
Компонент: [ClickHouse/QTickets API/DataLens/и т.д.]
Время возникновения: YYYY-MM-DD HH:MM:SS
Описание проблемы:
[Подробное описание]

Шаги воспроизведения:
1. [Шаг 1]
2. [Шаг 2]
3. [Шаг 3]

Ожидаемый результат:
[Что должно произойти]

Фактический результат:
[Что произошло на самом деле]

Дополнительная информация:
[Логи, скриншоты, ошибки]

Срочность: [Низкая/Средняя/Высокая/Критическая]
```

---

## ЗАКЛЮЧЕНИЕ

Данное руководство предоставляет комплексный подход к диагностике и решению проблем в системе Zakaz Dashboard. Регулярное использование проверочных скриптов и мониторинга позволит обеспечить стабильную работу системы и быстрое решение возникающих проблем.

**Ключевые рекомендации:**

1. **Регулярно выполняйте проверки** - ежедневные и еженедельные
2. **Мониторьте ключевые метрики** - свежесть данных, производительность, доступность
3. **Автоматизируйте восстановление** - где это возможно
4. **Ведите документацию** - фиксируйте все изменения и решения
5. **Обучайте команду** - обеспечьте передачу знаний

---

**Версия документа**: 1.0.0  
**Дата создания**: $(date +%Y-%m-%d)  
**Последнее обновление**: $(date +%Y-%m-%d)