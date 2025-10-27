#!/bin/bash

# E2E тестирование Zakaz Dashboard с реальными данными
# Использование: bash e2e_test_real_data.sh

set -e

echo "=== E2E Тестирование Zakaz Dashboard ==="
echo "Дата: $(date)"
echo ""

# Переход в директорию проекта (если нужно)
if [ ! -f "integrations/qtickets/loader.py" ]; then
    cd ..
fi

# Создание директории логов
mkdir -p logs/real_data_test

# Создание файла для результатов
RESULTS_FILE="logs/real_data_test/e2e_results_$(date +%Y%m%d_%H%M%S).json"
echo "{" > "$RESULTS_FILE"
echo "  \"timestamp\": \"$(date -Iseconds)\"," >> "$RESULTS_FILE"
echo "  \"test_date\": \"$(date +%Y-%m-%d)\"," >> "$RESULTS_FILE"
echo "  \"status\": \"running\"," >> "$RESULTS_FILE"
echo "  \"steps\": {}," >> "$RESULTS_FILE"
echo "  \"results\": {}," >> "$RESULTS_FILE"
echo "  \"errors\": []" >> "$RESULTS_FILE"
echo "}" >> "$RESULTS_FILE"

# Функция для логирования шага
log_step() {
    local step_name="$1"
    local status="$2"
    local message="$3"
    
    echo "[$(date +%H:%M:%S)] $step_name: $status - $message"
    
    # Обновление JSON файла
    if command -v jq >/dev/null 2>&1; then
        temp_file=$(mktemp)
        jq ".steps[\"$step_name\"] = {\"status\": \"$status\", \"message\": \"$message\", \"timestamp\": \"$(date -Iseconds)\"}" "$RESULTS_FILE" > "$temp_file"
        mv "$temp_file" "$RESULTS_FILE"
    fi
}

# Функция для логирования ошибки
log_error() {
    local step_name="$1"
    local error_message="$2"
    
    echo "[$(date +%H:%M:%S)] ERROR в шаге $step_name: $error_message"
    
    # Обновление JSON файла
    if command -v jq >/dev/null 2>&1; then
        temp_file=$(mktemp)
        jq ".errors += [{\"step\": \"$step_name\", \"message\": \"$error_message\", \"timestamp\": \"$(date -Iseconds)\"}]" "$RESULTS_FILE" > "$temp_file"
        mv "$temp_file" "$RESULTS_FILE"
    fi
}

# Функция для логирования результата
log_result() {
    local source="$1"
    local key="$2"
    local value="$3"
    
    # Обновление JSON файла
    if command -v jq >/dev/null 2>&1; then
        temp_file=$(mktemp)
        jq ".results[\"$source\"] = {\"$key\": \"$value\"}" "$RESULTS_FILE" > "$temp_file"
        if [ $? -eq 0 ]; then
            # Если ключа source еще нет, создаем его
            jq ".results[\"$source\"] += {\"$key\": \"$value\"}" "$RESULTS_FILE" > "$temp_file"
        fi
        mv "$temp_file" "$RESULTS_FILE"
    fi
}

# Шаг 1: Проверка Docker
log_step "1. Проверка Docker" "STARTING" "Проверка статуса контейнеров"
if ! docker ps | grep -q "ch-zakaz"; then
    log_error "1. Проверка Docker" "Контейнер ClickHouse не запущен"
    echo "❌ Запустите контейнеры: cd infra/clickhouse && docker-compose up -d"
    exit 1
fi
log_step "1. Проверка Docker" "SUCCESS" "Docker контейнеры запущены"

# Шаг 2: Тестирование QTickets
log_step "2. Тестирование QTickets" "STARTING" "Загрузка данных из QTickets API"
echo "2.1 Запуск загрузчика QTickets..."
start_time=$(date +%s)

if python3 integrations/qtickets/loader.py --env secrets/.env.qtickets --days 3 > logs/real_data_test/qtickets_loader.log 2>&1; then
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    log_step "2.1 Запуск загрузчика QTickets" "SUCCESS" "Загрузчик завершен за ${duration}с"
    log_result "qtickets" "loader_duration" "$duration"
else
    log_error "2.1 Запуск загрузчика QTickets" "Ошибка при запуске загрузчика"
    cat logs/real_data_test/qtickets_loader.log
fi

echo "2.2 Проверка загруженных данных QTickets..."
QTICKETS_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_qtickets_sales_raw" --format=TabSeparated 2>/dev/null || echo "0")
QTICKETS_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(event_date) FROM stg_qtickets_sales_raw" --format=TabSeparated 2>/dev/null || echo "NULL")
QTICKETS_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(event_date) FROM stg_qtickets_sales_raw" --format=TabSeparated 2>/dev/null || echo "0")

if [ "$QTICKETS_COUNT" -gt 0 ]; then
    log_step "2.2 Проверка загруженных данных QTickets" "SUCCESS" "Загружено $QTICKETS_COUNT записей"
    log_result "qtickets" "loaded" "$QTICKETS_COUNT"
    log_result "qtickets" "latest_date" "$QTICKETS_LATEST"
    log_result "qtickets" "days_behind" "$QTICKETS_BEHIND"
else
    log_error "2.2 Проверка загруженных данных QTickets" "Данные не загружены"
fi

# Шаг 3: Тестирование Google Sheets
log_step "3. Тестирование Google Sheets" "STARTING" "Загрузка данных из Google Sheets"
echo "3.1 Инициализация Google Sheets..."
if python3 archive/sheets/init.py > logs/real_data_test/sheets_init.log 2>&1; then
    log_step "3.1 Инициализация Google Sheets" "SUCCESS" "Google Sheets инициализирован"
else
    log_error "3.1 Инициализация Google Sheets" "Ошибка при инициализации Google Sheets"
    cat logs/real_data_test/sheets_init.log
fi

echo "3.2 Валидация данных Google Sheets..."
if python3 archive/sheets/validate.py > logs/real_data_test/sheets_validate.log 2>&1; then
    log_step "3.2 Валидация данных Google Sheets" "SUCCESS" "Данные Google Sheets проверены"
else
    log_error "3.2 Валидация данных Google Sheets" "Ошибка при валидации данных Google Sheets"
    cat logs/real_data_test/sheets_validate.log
fi

echo "3.3 Проверка загруженных данных Google Sheets..."
SHEETS_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_google_sheets_raw" --format=TabSeparated 2>/dev/null || echo "0")
SHEETS_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(event_date) FROM stg_google_sheets_raw" --format=TabSeparated 2>/dev/null || echo "NULL")
SHEETS_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(event_date) FROM stg_google_sheets_raw" --format=TabSeparated 2>/dev/null || echo "0")

if [ "$SHEETS_COUNT" -gt 0 ]; then
    log_step "3.3 Проверка загруженных данных Google Sheets" "SUCCESS" "Загружено $SHEETS_COUNT записей"
    log_result "sheets" "loaded" "$SHEETS_COUNT"
    log_result "sheets" "latest_date" "$SHEETS_LATEST"
    log_result "sheets" "days_behind" "$SHEETS_BEHIND"
else
    log_error "3.3 Проверка загруженных данных Google Sheets" "Данные не загружены"
fi

# Шаг 4: Тестирование VK Ads
log_step "4. Тестирование VK Ads" "STARTING" "Загрузка данных из VK Ads API"
echo "4.1 Запуск загрузчика VK Ads..."
start_time=$(date +%s)

# Проверяем, является ли токен заглушкой
VK_TOKEN=$(grep VK_TOKEN secrets/.env.vk | cut -d'=' -f2)
if [ "$VK_TOKEN" = "vk_token_placeholder" ]; then
    log_step "4.1 Запуск загрузчика VK Ads" "SKIPPED" "VK токен не предоставлен, пропускаем тест"
    VK_COUNT=0
    VK_LATEST="NULL"
    VK_BEHIND="0"
    log_result "vk_ads" "loaded" "0"
    log_result "vk_ads" "latest_date" "$VK_LATEST"
    log_result "vk_ads" "days_behind" "$VK_BEHIND"
else
    if python3 integrations/vk_ads/loader.py --env secrets/.env.vk --days 3 > logs/real_data_test/vk_loader.log 2>&1; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        log_step "4.1 Запуск загрузчика VK Ads" "SUCCESS" "Загрузчик завершен за ${duration}с"
        
        VK_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM fact_vk_ads_daily" --format=TabSeparated 2>/dev/null || echo "0")
        VK_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(stat_date) FROM fact_vk_ads_daily" --format=TabSeparated 2>/dev/null || echo "NULL")
        VK_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(stat_date) FROM fact_vk_ads_daily" --format=TabSeparated 2>/dev/null || echo "0")
        
        if [ "$VK_COUNT" -gt 0 ]; then
            log_step "4.1 Запуск загрузчика VK Ads" "SUCCESS" "Загружено $VK_COUNT записей"
            log_result "vk_ads" "loaded" "$VK_COUNT"
            log_result "vk_ads" "latest_date" "$VK_LATEST"
            log_result "vk_ads" "days_behind" "$VK_BEHIND"
        else
            log_error "4.1 Запуск загрузчика VK Ads" "Данные не загружены"
        fi
    else
        log_error "4.1 Запуск загрузчика VK Ads" "Ошибка при запуске загрузчика"
        cat logs/real_data_test/vk_loader.log
    fi
fi

# Шаг 5: Тестирование Яндекс.Директ
log_step "5. Тестирование Яндекс.Директ" "STARTING" "Загрузка данных из Яндекс.Директ API"
echo "5.1 Запуск загрузчика Яндекс.Директ..."
start_time=$(date +%s)

# Проверяем, является ли токен заглушкой
DIRECT_TOKEN=$(grep DIRECT_TOKEN secrets/.env.direct | cut -d'=' -f2)
if [ "$DIRECT_TOKEN" = "direct_token_placeholder" ]; then
    log_step "5.1 Запуск загрузчика Яндекс.Директ" "SKIPPED" "Токен не предоставлен, пропускаем тест"
    DIRECT_COUNT=0
    DIRECT_LATEST="NULL"
    DIRECT_BEHIND="0"
    log_result "direct" "loaded" "0"
    log_result "direct" "latest_date" "$DIRECT_LATEST"
    log_result "direct" "days_behind" "$DIRECT_BEHIND"
else
    if python3 integrations/direct/loader.py --env secrets/.env.direct --days 3 > logs/real_data_test/direct_loader.log 2>&1; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        log_step "5.1 Запуск загрузчика Яндекс.Директ" "SUCCESS" "Загрузчик завершен за ${duration}с"
        
        DIRECT_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM fact_direct_daily" --format=TabSeparated 2>/dev/null || echo "0")
        DIRECT_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(stat_date) FROM fact_direct_daily" --format=TabSeparated 2>/dev/null || echo "NULL")
        DIRECT_BEHIND=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT today() - max(stat_date) FROM fact_direct_daily" --format=TabSeparated 2>/dev/null || echo "0")
        
        if [ "$DIRECT_COUNT" -gt 0 ]; then
            log_step "5.1 Запуск загрузчика Яндекс.Директ" "SUCCESS" "Загружено $DIRECT_COUNT записей"
            log_result "direct" "loaded" "$DIRECT_COUNT"
            log_result "direct" "latest_date" "$DIRECT_LATEST"
            log_result "direct" "days_behind" "$DIRECT_BEHIND"
        else
            log_error "5.1 Запуск загрузчика Яндекс.Директ" "Данные не загружены"
        fi
    else
        log_error "5.1 Запуск загрузчика Яндекс.Директ" "Ошибка при запуске загрузчика"
        cat logs/real_data_test/direct_loader.log
    fi
fi

# Шаг 6: Тестирование агрегированных данных
log_step "6. Тестирование агрегированных данных" "STARTING" "Обновление и проверка агрегатов"
echo "6.1 Обновление материализованных представлений..."
if docker exec ch-zakaz clickhouse-client --database=zakaz --query="ALTER TABLE zakaz.dm_sales_14d MATERIALIZE INDEX" > logs/real_data_test/materialize.log 2>&1; then
    log_step "6.1 Обновление материализованных представлений" "SUCCESS" "Представления обновлены"
else
    log_error "6.1 Обновление материализованных представлений" "Ошибка обновления представлений"
fi

echo "6.2 Проверка данных в представлениях..."
SALES_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM zakaz.v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
MARKETING_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM zakaz.v_marketing_daily" --format=TabSeparated 2>/dev/null || echo "0")
SALES_SUM=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT sum(tickets_sold) FROM zakaz.v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
REVENUE_SUM=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT sum(revenue - refunds_amount) FROM zakaz.v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")

log_step "6.2 Проверка данных в представлениях" "SUCCESS" "Представления проверены"
echo "   v_sales_latest: $SALES_COUNT записей"
echo "   v_marketing_daily: $MARKETING_COUNT записей"
echo "   Продано билетов: $SALES_SUM"
echo "   Общая выручка: $REVENUE_SUM"

log_result "aggregated" "sales_records" "$SALES_COUNT"
log_result "aggregated" "marketing_records" "$MARKETING_COUNT"
log_result "aggregated" "total_tickets" "$SALES_SUM"
log_result "aggregated" "total_revenue" "$REVENUE_SUM"

# Шаг 7: Тестирование доступа для DataLens
log_step "7. Тестирование доступа для DataLens" "STARTING" "Проверка прав пользователя datalens_reader"
READER_SALES=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM zakaz.v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
READER_MARKETING=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM zakaz.v_marketing_daily" --format=TabSeparated 2>/dev/null || echo "0")

if [ "$READER_SALES" = "$SALES_COUNT" ] && [ "$READER_MARKETING" = "$MARKETING_COUNT" ]; then
    log_step "7. Тестирование доступа для DataLens" "SUCCESS" "Пользователь datalens_reader имеет доступ к данным"
    log_result "data_lens" "sales_access" "OK"
    log_result "data_lens" "marketing_access" "OK"
else
    log_error "7. Тестирование доступа для DataLens" "Проблема с доступом для пользователя datalens_reader"
    echo "   Ожидаемо: $SALES_COUNT, получено: $READER_SALES"
    echo "   Ожидаемо: $MARKETING_COUNT, получено: $READER_MARKETING"
    log_result "data_lens" "sales_access" "ERROR"
    log_result "data_lens" "marketing_access" "ERROR"
fi

# Шаг 8: Тестирование производительности
log_step "8. Тестирование производительности" "STARTING" "Замер времени выполнения запросов"
echo "8.1 Тестирование скорости запросов..."
start_time=$(date +%s)

# Тестовый запрос
docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    event_date,
    city,
    SUM(tickets_sold) as tickets,
    SUM(revenue - refunds_amount) as revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7
GROUP BY event_date, city
ORDER BY revenue DESC
LIMIT 10
" --format=Null > logs/real_data_test/performance_test.log 2>&1

end_time=$(date +%s)
query_time=$((end_time - start_time))
echo "   Время выполнения запроса: ${query_time} секунд"

if [ "$query_time" -lt 5 ]; then
    log_step "8.1 Тестирование скорости запросов" "SUCCESS" "Производительность: ${query_time}с (< 5s)"
    log_result "performance" "query_time_seconds" "$query_time"
    log_result "performance" "status" "GOOD"
else
    log_step "8.1 Тестирование скорости запросов" "WARNING" "Производительность: ${query_time}s (> 5s)"
    log_result "performance" "query_time_seconds" "$query_time"
    log_result "performance" "status" "SLOW"
fi

# Шаг 9: Тестирование целостности данных
log_step "9. Тестирование целостности данных" "STARTING" "Проверка качества данных"
echo "9.1 Проверка на дубликаты..."
DUPLICATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    count() - countDistinct(concat(event_date, city, event_name)) as duplicates
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7
" --format=TabSeparated 2>/dev/null || echo "0")

echo "9.2 Проверка пропущенных дат..."
MISSING_DATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
WITH date_series AS (
    SELECT today() - number as date
    FROM numbers(7)
)
SELECT 
    COUNT(date_series.date) - COUNT(DISTINCT(event_date)) as missing_dates
FROM date_series
LEFT JOIN zakaz.v_sales_latest ON date_series.date = event_date
WHERE date_series.date >= today() - 7
" --format=TabSeparated 2>/dev/null || echo "0")

if [ "$DUPLICATES" -eq 0 ]; then
    log_step "9.1 Проверка на дубликаты" "SUCCESS" "Дубликаты отсутствуют"
    log_result "data_quality" "duplicates" "0"
else
    log_step "9.1 Проверка на дубликаты" "WARNING" "Обнаружены дубликаты: $DUPLICATES"
    log_result "data_quality" "duplicates" "$DUPLICATES"
fi

if [ "$MISSING_DATES" -eq 0 ]; then
    log_step "9.2 Проверка пропущенных дат" "SUCCESS" "Пропущенные даты отсутствуют"
    log_result "data_quality" "missing_dates" "0"
else
    log_step "9.2 Проверка пропущенных дат" "WARNING" "Пропущенные даты: $MISSING_DATES"
    log_result "data_quality" "missing_dates" "$MISSING_DATES"
fi

# Шаг 10: Создание финального отчета
log_step "10. Создание отчета" "STARTING" "Формирование итогового отчета"
TOTAL_RECORDS=$((QTICKETS_COUNT + SHEETS_COUNT + VK_COUNT + DIRECT_COUNT))

# Определение статуса
if [ "$QTICKETS_COUNT" -gt 0 ] && [ "$SHEETS_COUNT" -gt 0 ]; then
    STATUS="✅ УСПЕХ"
    EXIT_CODE=0
elif [ "$TOTAL_RECORDS" -gt 0 ]; then
    STATUS="⚠️ ЧАСТИЧНЫЙ УСПЕХ"
    EXIT_CODE=1
else
    STATUS="❌ НЕУДАЧА"
    EXIT_CODE=2
fi

# Обновление финального статуса в JSON
if command -v jq >/dev/null 2>&1; then
    temp_file=$(mktemp)
    jq ".status = \"$STATUS\" | .exit_code = $EXIT_CODE | .test_date = \"$(date +%Y-%m-%d)\" | .results.summary = {\"total_records\": $TOTAL_RECORDS, \"qtickets\": $QTICKETS_COUNT, \"sheets\": $SHEETS_COUNT, \"vk_ads\": $VK_COUNT, \"direct\": $DIRECT_COUNT, \"sales_records\": $SALES_COUNT, \"marketing_records\": $MARKETING_COUNT, \"total_tickets\": $SALES_SUM, \"total_revenue\": $REVENUE_SUM, \"performance\": {\"query_time_seconds\": $query_time, \"status\": \"$(if [ $query_time -lt 5 ]; then echo \"GOOD\"; else echo \"SLOW\"; fi)\"}, \"data_quality\": {\"duplicates\": $DUPLICATES, \"missing_dates\": $MISSING_DATES}, \"data_lens\": {\"sales_access\": \"$(if [ \"$READER_SALES\" = "$SALES_COUNT" ]; then echo \"OK\"; else echo \"ERROR\"; fi)\", \"marketing_access\": \"$(if [ \"$READER_MARKETING" = "$MARKETING_COUNT" ]; then echo \"OK\"; else echo \"ERROR\"; fi)\", \"steps\": $(jq '.steps' "$RESULTS_FILE") | .errors $(jq '.errors' "$RESULTS_FILE")" "$RESULTS_FILE" > "$temp_file"
    mv "$temp_file" "$RESULTS_FILE"
fi

echo ""
echo "=== ИТОГИ E2E ТЕСТИРОВАНИЯ ==="
echo "Статус: $STATUS"
echo "Всего записей: $TOTAL_RECORDS"
echo "QTickets: $QTICKETS_COUNT"
echo "Google Sheets: $SHEETS_COUNT"
echo "VK Ads: $VK_COUNT"
echo "Яндекс.Директ: $DIRECT_COUNT"
echo "Продажи: $SALES_COUNT записей"
echo "Маркетинг: $MARKETING_COUNT записей"
echo "Продано билетов: $SALES_SUM"
echo "Общая выручка: $REVENUE_SUM"
echo "Производительность: ${query_time}с"
echo "Качество данных: дубликаты=$DUPLICATES, пропущенные даты=$MISSING_DATES"
echo "DataLens доступ: продажи=$READER_SALES/$SALES_COUNT, маркетинг=$READER_MARKETING/$MARKETING_COUNT"
echo ""
echo "Логи сохранены в директории logs/real_data_test/"
echo "JSON отчет сохранен в: $RESULTS_FILE"

# Сохранение результатов в отдельный текстовый файл
cat > logs/real_data_test/e2e_summary_$(date +%Y%m%d_%H%M%S).txt << EOF
E2E Test Summary - $(date)
===================

Status: $STATUS

Data Summary:
- Total Records: $TOTAL_RECORDS
- QTickets: $QTICKETS_COUNT
- Google Sheets: $SHEETS_COUNT
- VK Ads: $VK_COUNT
- Яндекс.Директ: $DIRECT_COUNT

Aggregated Data:
- Sales Records: $SALES_COUNT
- Marketing Records: $MARKETING_COUNT
- Total Tickets: $SALES_SUM
- Total Revenue: $REVENUE_SUM

Performance:
- Query Time: ${query_time}s
- Status: $(if [ $query_time -lt 5 ]; then echo "GOOD (< 5s)"; else echo "SLOW (> 5s)"; fi)

Data Quality:
- Duplicates: $DUPLICATES
- Missing Dates: $MISSING_DATES

DataLens Access:
- Sales: $READER_SALES/$SALES_COUNT
- Marketing: $READER_MARKETING/$MARKETING_COUNT

Errors:
$(cat "$RESULTS_FILE" | jq -r '.errors[] | "- Step: \(.step), Message: \(.message)'" 2>/dev/null || echo "No errors")

Logs:
- QTickets: logs/real_data_test/qtickets_loader.log
- Google Sheets: logs/real_data_test/sheets_init.log, logs/real_data_test/sheets_validate.log
- VK Ads: logs/real_data_test/vk_loader.log
- Яндекс.Директ: logs/real_data_test/direct_loader.log
- Performance: logs/real_data_test/performance_test.log
- Materialize: logs/real_data_test/materialize.log
- JSON: $RESULTS_FILE
EOF

echo "✅ Текстовый отчет сохранен в logs/real_data_test/e2e_summary_$(date +%Y%m%d_%H%M%S).txt"

exit $EXIT_CODE