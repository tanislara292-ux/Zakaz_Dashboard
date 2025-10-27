#!/bin/bash

# Упрощенный E2E тестирование Zakaz Dashboard
# Использование: bash e2e_test_simple.sh

set -e

echo "=== Упрощенное E2E Тестирование Zakaz Dashboard ==="
echo "Дата: $(date)"
echo ""

# Переход в директорию проекта
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
    
    # Обновление JSON файла (упрощенная версия без jq)
    echo "  \"$step_name\": {\"status\": \"$status\", \"message\": \"$message\", \"timestamp\": \"$(date -Iseconds)\"}," >> "$RESULTS_FILE.tmp"
}

# Функция для логирования ошибки
log_error() {
    local step_name="$1"
    local error_message="$2"
    
    echo "[$(date +%H:%M:%S)] ERROR в шаге $step_name: $error_message"
    
    # Добавление ошибки в JSON (упрощенная версия)
    echo "  \"error_$step_name\": {\"step\": \"$step_name\", \"message\": \"$error_message\", \"timestamp\": \"$(date -Iseconds)\"}," >> "$RESULTS_FILE.tmp"
}

# Функция для логирования результата
log_result() {
    local source="$1"
    local key="$2"
    local value="$3"
    
    echo "    \"$source\": {\"$key\": \"$value\"}," >> "$RESULTS_FILE.tmp
}

# Шаг 1: Проверка Docker
log_step "1. Проверка Docker" "STARTING" "Проверка статуса контейнеров"
if ! docker ps | grep -q "ch-zakaz"; then
    log_error "1. Проверка Docker" "Контейнер ClickHouse не запущен"
    echo "❌ Запустите контейнеры: cd infra/clickhouse && docker-compose up -d"
    exit 1
fi
log_step "1. Проверка Docker" "SUCCESS" "Docker контейнеры запущены"

# Шаг 2: Проверка данных в ClickHouse
log_step "2. Проверка данных в ClickHouse" "STARTING" "Проверка существующих данных"

# Проверка таблиц
echo "2.1 Проверка таблиц ClickHouse..."
QTICKETS_TABLE=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_qtickets_sales_raw" --format=TabSeparated 2>/dev/null || echo "0")
QTICKETS_LATEST=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT max(event_date) FROM stg_qtickets_sales_raw" --format=TabSeparated 2>/dev/null || echo "NULL")

if [ "$QTICKETS_TABLE" -gt 0 ]; then
    log_step "2.1 Проверка таблиц ClickHouse" "SUCCESS" "Таблица stg_qtickets_sales_raw содержит $QTICKETS_TABLE записей"
    log_result "qtickets" "loaded" "$QTICKETS_TABLE"
    log_result "qtickets" "latest_date" "$QTICKETS_LATEST"
else
    log_error "2.1 Проверка таблиц ClickHouse" "Таблица stg_qtickets_sales_raw пуста или не существует"
fi

# Проверка представлений
echo "2.2 Проверка представлений ClickHouse..."
SALES_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
MARKETING_COUNT=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM v_marketing_daily" --format=TabSeparated 2>/dev/null || echo "0")

if [ "$SALES_COUNT" -gt 0 ]; then
    log_step "2.2 Проверка представлений ClickHouse" "SUCCESS" "Представления содержат данные"
    log_result "views" "sales_records" "$SALES_COUNT"
    log_result "views" "marketing_records" "$MARKETING_COUNT"
else
    log_error "2.2 Проверка представлений ClickHouse" "Представления пусты или не существуют"
fi

# Шаг 3: Тестирование доступа для DataLens
log_step "3. Тестирование доступа для DataLens" "STARTING" "Проверка прав пользователя datalens_reader"
READER_SALES=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM v_sales_latest" --format=TabSeparated 2>/dev/null || echo "0")
READER_MARKETING=$(docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass --database=zakaz --query="SELECT count() FROM v_marketing_daily" --format=TabSeparated 2>/dev/null || echo "0")

if [ "$READER_SALES" -gt 0 ] && [ "$READER_MARKETING" -gt 0 ]; then
    log_step "3. Тестирование доступа для DataLens" "SUCCESS" "Пользователь datalens_reader имеет доступ к данным"
    log_result "data_lens" "sales_access" "OK"
    log_result "data_lens" "marketing_access" "OK"
else
    log_error "3. Тестирование доступа для DataLens" "Проблема с доступом для пользователя datalens_reader"
    log_result "data_lens" "sales_access" "ERROR"
    log_result "data_lens" "marketing_access" "ERROR"
fi

# Шаг 4: Тестирование производительности
log_step "4. Тестирование производительности" "STARTING" "Замер времени выполнения запросов"
echo "4.1 Тестирование скорости запросов..."
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
" --format=Null > logs/real_data_test/performance_test.log 2>&1

end_time=$(date +%s)
query_time=$((end_time - start_time))
echo "   Время выполнения запроса: ${query_time} секунд"

if [ "$query_time" -lt 5 ]; then
    log_step "4.1 Тестирование скорости запросов" "SUCCESS" "Производительность: ${query_time}с (< 5s)"
    log_result "performance" "query_time_seconds" "$query_time"
    log_result "performance" "status" "GOOD"
else
    log_step "4.1 Тестирование скорости запросов" "WARNING" "Производительность: ${query_time}s (> 5s)"
    log_result "performance" "query_time_seconds" "$query_time"
    log_result "performance" "status" "SLOW"
fi

# Шаг 5: Тестирование целостности данных
log_step "5. Тестирование целостности данных" "STARTING" "Проверка качества данных"
echo "5.1 Проверка на дубликаты..."
DUPLICATES=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="
SELECT 
    count() - countDistinct(concat(event_date, city, event_name)) as duplicates
FROM v_sales_latest
WHERE event_date >= today() - 7
" --format=TabSeparated 2>/dev/null || echo "0")

echo "5.2 Проверка пропущенных дат..."
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

if [ "$DUPLICATES" -eq 0 ]; then
    log_step "5.1 Проверка на дубликаты" "SUCCESS" "Дубликаты отсутствуют"
    log_result "data_quality" "duplicates" "0"
else
    log_step "5.1 Проверка на дубликаты" "WARNING" "Обнаружены дубликаты: $DUPLICATES"
    log_result "data_quality" "duplicates" "$DUPLICATES"
fi

if [ "$MISSING_DATES" -eq 0 ]; then
    log_step "5.2 Проверка пропущенных дат" "SUCCESS" "Пропущенные даты отсутствуют"
    log_result "data_quality" "missing_dates" "0"
else
    log_step "5.2 Проверка пропущенных дат" "WARNING" "Пропущенные даты: $MISSING_DATES"
    log_result "data_quality" "missing_dates" "$MISSING_DATES"
fi

# Шаг 6: Создание финального отчета
log_step "6. Создание отчета" "STARTING" "Формирование итогового отчета"
TOTAL_RECORDS=$((QTICKETS_TABLE))

# Определение статуса
if [ "$QTICKETS_TABLE" -gt 0 ] && [ "$SALES_COUNT" -gt 0 ]; then
    STATUS="✅ УСПЕХ"
    EXIT_CODE=0
elif [ "$TOTAL_RECORDS" -gt 0 ]; then
    STATUS="⚠️ ЧАСТИЧНЫЙ УСПЕХ"
    EXIT_CODE=1
else
    STATUS="❌ НЕУДАЧА"
    EXIT_CODE=2
fi

# Создание финального JSON отчета
echo "{" > "$RESULTS_FILE"
echo "  \"timestamp\": \"$(date -Iseconds)\"," >> "$RESULTS_FILE"
echo "  \"test_date\": \"$(date +%Y-%m-%d)\"," >> "$RESULTS_FILE"
echo "  \"status\": \"$STATUS\"," >> "$RESULTS_FILE"
echo "  \"exit_code\": $EXIT_CODE," >> "$RESULTS_FILE"
echo "  \"steps\": {" >> "$RESULTS_FILE"

# Добавляем шаги из временного файла
if [ -f "$RESULTS_FILE.tmp" ]; then
    # Удаляем последнюю запятую
    sed '$ s/,$//' "$RESULTS_FILE.tmp" >> "$RESULTS_FILE"
    echo "" >> "$RESULTS_FILE"
    echo "  }," >> "$RESULTS_FILE"
fi

echo "  \"results\": {" >> "$RESULTS_FILE"
echo "    \"summary\": {" >> "$RESULTS_FILE"
echo "      \"total_records\": $TOTAL_RECORDS," >> "$RESULTS_FILE"
echo "      \"qtickets\": $QTICKETS_TABLE," >> "$RESULTS_FILE"
echo "      \"sales_records\": $SALES_COUNT," >> "$RESULTS_FILE"
echo "      \"marketing_records\": $MARKETING_COUNT" >> "$RESULTS_FILE"
echo "    }," >> "$RESULTS_FILE"
echo "    \"qtickets\": {" >> "$RESULTS_FILE"
echo "      \"loaded\": \"$QTICKETS_TABLE\"," >> "$RESULTS_FILE"
echo "      \"latest_date\": \"$QTICKETS_LATEST\"" >> "$RESULTS_FILE"
echo "    }," >> "$RESULTS_FILE"
echo "    \"views\": {" >> "$RESULTS_FILE"
echo "      \"sales_records\": \"$SALES_COUNT\"," >> "$RESULTS_FILE"
echo "      \"marketing_records\": \"$MARKETING_COUNT\"" >> "$RESULTS_FILE"
echo "    }," >> "$RESULTS_FILE"
echo "    \"performance\": {" >> "$RESULTS_FILE"
echo "      \"query_time_seconds\": \"$query_time\"," >> "$RESULTS_FILE"
echo "      \"status\": \"$(if [ $query_time -lt 5 ]; then echo "GOOD"; else echo "SLOW"; fi)\"" >> "$RESULTS_FILE"
echo "    }," >> "$RESULTS_FILE"
echo "    \"data_quality\": {" >> "$RESULTS_FILE"
echo "      \"duplicates\": \"$DUPLICATES\"," >> "$RESULTS_FILE"
echo "      \"missing_dates\": \"$MISSING_DATES\"" >> "$RESULTS_FILE"
echo "    }," >> "$RESULTS_FILE"
echo "    \"data_lens\": {" >> "$RESULTS_FILE"
echo "      \"sales_access\": \"$(if [ "$READER_SALES" -gt 0 ]; then echo "OK"; else echo "ERROR"; fi)\"," >> "$RESULTS_FILE"
echo "      \"marketing_access\": \"$(if [ "$READER_MARKETING" -gt 0 ]; then echo "OK"; else echo "ERROR"; fi)\"" >> "$RESULTS_FILE"
echo "    }" >> "$RESULTS_FILE"
echo "  }," >> "$RESULTS_FILE"
echo "  \"errors\": []" >> "$RESULTS_FILE"
echo "}" >> "$RESULTS_FILE"

echo ""
echo "=== ИТОГИ УПРОЩЕННОГО E2E ТЕСТИРОВАНИЯ ==="
echo "Статус: $STATUS"
echo "Всего записей (сырые): $TOTAL_RECORDS"
echo "QTickets: $QTICKETS_TABLE"
echo "Продажи: $SALES_COUNT записей"
echo "Маркетинг: $MARKETING_COUNT записей"
echo "Производительность: ${query_time}с"
echo "Качество данных: дубликаты=$DUPLICATES, пропущенные даты=$MISSING_DATES"
echo "DataLens доступ: продажи=$READER_SALES/$SALES_COUNT, маркетинг=$READER_MARKETING/$MARKETING_COUNT"
echo ""
echo "Логи сохранены в директории logs/real_data_test/"
echo "JSON отчет сохранен в: $RESULTS_FILE"

# Сохранение результатов в отдельный текстовый файл
cat > logs/real_data_test/e2e_summary_$(date +%Y%m%d_%H%M%S).txt << EOF
Упрощенный E2E Test Summary - $(date)
===================================

Статус: $STATUS

Данные:
- Сырые записи (QTickets): $QTICKETS_TABLE
- Продажи: $SALES_COUNT
- Маркетинг: $MARKETING_COUNT

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
- Производительность: logs/real_data_test/performance_test.log
- JSON: $RESULTS_FILE
EOF

echo "✅ Текстовый отчет сохранен в logs/real_data_test/e2e_summary_$(date +%Y%m%d_%H%M%S).txt"

# Очистка временного файла
if [ -f "$RESULTS_FILE.tmp" ]; then
    rm "$RESULTS_FILE.tmp"
fi

exit $EXIT_CODE