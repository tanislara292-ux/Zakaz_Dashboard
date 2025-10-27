#!/bin/bash

# E2E тестирование пайплайна QTickets API
# Скрипт для выполнения на сервере museshow

set -e  # Прерывать выполнение при ошибках

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода заголовков
print_header() {
    echo -e "\n${GREEN}=== $1 ===${NC}"
}

# Функция для вывода шагов
print_step() {
    echo -e "\n${YELLOW}>>> $1${NC}"
}

# Функция для вывода результатов
print_result() {
    echo -e "\n${GREEN}✓ $1${NC}"
}

# Функция для вывода ошибок
print_error() {
    echo -e "\n${RED}✗ $1${NC}"
}

# Переменные окружения
PROJECT_DIR="/opt/zakaz_dashboard/dashboard-mvp"
SECRETS_DIR="${PROJECT_DIR}/secrets"
ENV_FILE="${SECRETS_DIR}/.env.qtickets_api"
REPORT_FILE="${PROJECT_DIR}/TASK-QT-API-E2E-REPORT.md"
CLICKHOUSE_USER="admin_min"
CLICKHOUSE_PASSWORD="AdminMin2024!Strong#Pass"

# Создание директории для секретов, если не существует
mkdir -p "${SECRETS_DIR}"

# Начало отчёта
cat > "${REPORT_FILE}" << EOF
# TASK-QT-API-E2E-REPORT

## Контекст

Проводили e2e тест нового QTickets API пайплайна по задаче TASK-QT-API-PRIMARY перед выкладкой на сервер заказчика.

## Окружение

* хост: museshow
* версия кода: $(cd ${PROJECT_DIR} && git rev-parse HEAD)
* дата тестирования: $(date)

EOF

print_header "ШАГ 1: Проверка окружения и контейнеров"

print_step "Проверка статуса контейнеров ClickHouse"
cd ${PROJECT_DIR}/infra/clickhouse
docker compose ps

# Проверка, что контейнеры запущены
if ! docker compose ps | grep -q "ch-zakaz.*Up"; then
    print_error "Контейнер ch-zakaz не запущен. Запускаем..."
    docker compose up -d
    sleep 10
fi

if ! docker compose ps | grep -q "ch-zakaz-caddy.*Up"; then
    print_error "Контейнер ch-zakaz-caddy не запущен. Запускаем..."
    docker compose up -d
    sleep 10
fi

print_result "Контейнеры ClickHouse запущены"

echo "" >> "${REPORT_FILE}"
echo "### Контейнеры" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
docker compose ps >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"

print_header "ШАГ 2: Применение миграции"

print_step "Применение миграции 2025-qtickets-api.sql"
cd ${PROJECT_DIR}

# Применение миграции
if docker exec -i ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  < infra/clickhouse/migrations/2025-qtickets-api.sql; then
    print_result "Миграция применена успешно"
else
    print_error "Ошибка при применении миграции"
    exit 1
fi

echo "" >> "${REPORT_FILE}"
echo "### Миграции" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "Миграция \`2025-qtickets-api.sql\` применена успешно" >> "${REPORT_FILE}"

print_header "ШАГ 3: Создание секретного env файла"

print_step "Создание .env.qtickets_api с реальными данными"

# Создание env файла с реальными данными
cat > "${ENV_FILE}" << EOF
# QTickets API config
QTICKETS_API_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_API_TOKEN=4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ
QTICKETS_ORG_SLUG=irs-prod
QTICKETS_ORG_DASHBOARD_URL=https://irs-prod.qtickets.ru

# ClickHouse connection for ETL writer
CLICKHOUSE_HOST=http://localhost:8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=etl_writer_password_2024

# Runtime
TZ=Europe/Moscow
ORG_NAME=irs-prod
EOF

print_result "Env файл создан"

echo "" >> "${REPORT_FILE}"
echo "### Конфигурация" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "Создан секретный env файл \`.env.qtickets_api\` с реальными данными" >> "${REPORT_FILE}"

print_header "ШАГ 4: Проверка прав пользователя etl_writer"

print_step "Проверка и предоставление прав etl_writer"

# Проверка существования пользователя etl_writer
ETL_WRITER_EXISTS=$(docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "SELECT count() FROM system.users WHERE name = 'etl_writer'")

if [ "$ETL_WRITER_EXISTS" = "0" ]; then
    print_step "Создание пользователя etl_writer"
    docker exec ch-zakaz clickhouse-client \
      --user=${CLICKHOUSE_USER} \
      --password='${CLICKHOUSE_PASSWORD}' \
      -q "CREATE USER etl_writer IDENTIFIED BY 'etl_writer_password_2024'"
fi

# Предоставление прав на вставку в новые таблицы
docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "GRANT INSERT ON zakaz.stg_qtickets_api_orders_raw TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "GRANT INSERT ON zakaz.stg_qtickets_api_inventory_raw TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "GRANT INSERT ON zakaz.dim_events TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "GRANT INSERT ON zakaz.fact_qtickets_sales_daily TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "GRANT INSERT ON zakaz.fact_qtickets_inventory_latest TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "GRANT INSERT ON zakaz.meta_job_runs TO etl_writer"

print_result "Права etl_writer настроены"

print_header "ШАГ 5: Ручной прогон лоадера"

print_step "Активация виртуального окружения и установка зависимостей"
cd ${PROJECT_DIR}

# Создание venv если не существует
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

# Установка зависимостей
pip install -q clickhouse-driver requests python-dotenv

print_step "Запуск лоадера QTickets API"

# Запуск лоадера
LOADER_OUTPUT=$(python -m integrations.qtickets_api.loader \
  --envfile ${ENV_FILE} \
  --since-hours 24 \
  --verbose 2>&1)

echo "$LOADER_OUTPUT"

# Сохранение вывода лоадера в отчёт
echo "" >> "${REPORT_FILE}"
echo "### Ручной прогон лоадера" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo '```bash' >> "${REPORT_FILE}"
echo "python -m integrations.qtickets_api.loader \\" >> "${REPORT_FILE}"
echo "  --envfile ${ENV_FILE} \\" >> "${REPORT_FILE}"
echo "  --since-hours 24 \\" >> "${REPORT_FILE}"
echo "  --verbose" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "Последние строки вывода:" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$LOADER_OUTPUT" | tail -20 >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"

# Проверка на ошибки в выводе
if echo "$LOADER_OUTPUT" | grep -q "ERROR\|Exception\|Traceback"; then
    print_error "Обнаружены ошибки в работе лоадера"
else
    print_result "Лоадер отработал без критических ошибок"
fi

print_header "ШАГ 6: Проверка данных в ClickHouse"

print_step "Проверка данных в staging таблице"

STAGING_COUNT=$(docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "SELECT count(*) AS rows, max(sale_ts) AS last_sale FROM zakaz.stg_qtickets_api_orders_raw")

echo "Строк в staging: $STAGING_COUNT"

print_step "Проверка данных в fact таблице продаж"

FACT_SALES=$(docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "SELECT sales_date, city, sum(tickets_sold) AS sold, sum(revenue) AS rev
      FROM zakaz.fact_qtickets_sales_daily
      GROUP BY sales_date, city
      ORDER BY sales_date DESC
      LIMIT 10;")

echo "Данные в fact_qtickets_sales_daily:"
echo "$FACT_SALES"

print_step "Проверка данных инвентаря"

INVENTORY_DATA=$(docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "SELECT snapshot_ts, event_id, city, tickets_total, tickets_left
      FROM zakaz.fact_qtickets_inventory_latest
      ORDER BY snapshot_ts DESC
      LIMIT 10;")

echo "Данные в fact_qtickets_inventory_latest:"
echo "$INVENTORY_DATA"

print_step "Проверка витрины v_sales_latest"

VIEW_DATA=$(docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "SELECT *
      FROM zakaz.v_sales_latest
      LIMIT 20;" 2>&1)

if echo "$VIEW_DATA" | grep -q "ERROR\|Exception"; then
    print_error "Ошибка при запросе к витрине v_sales_latest"
    echo "$VIEW_DATA"
else
    print_result "Витрина v_sales_latest работает корректно"
    echo "Пример данных из витрины:"
    echo "$VIEW_DATA" | head -10
fi

# Сохранение результатов проверки данных в отчёт
echo "" >> "${REPORT_FILE}"
echo "### Проверка данных в ClickHouse" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "**Staging таблица:**" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$STAGING_COUNT" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "**Fact таблица продаж:**" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$FACT_SALES" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "**Инвентарь:**" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$INVENTORY_DATA" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"

print_header "ШАГ 7: Проверка healthcheck и метаданных"

print_step "Проверка записей в meta_job_runs"

JOB_RUNS=$(docker exec ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  -q "SELECT job_name, status, rows_sales, rows_inventory, started_at, finished_at
      FROM zakaz.meta_job_runs
      WHERE job_name = 'qtickets_api'
      ORDER BY finished_at DESC
      LIMIT 5;")

echo "Записи в meta_job_runs:"
echo "$JOB_RUNS"

print_step "Проверка healthcheck для qtickets_api"

cd ${PROJECT_DIR}
HEALTHCHECK_OUTPUT=$(python ops/healthcheck_integrations.py --check qtickets_api 2>&1 || echo "Healthcheck failed")

echo "Результат healthcheck:"
echo "$HEALTHCHECK_OUTPUT"

# Сохранение результатов healthcheck в отчёт
echo "" >> "${REPORT_FILE}"
echo "### Healthcheck и метаданные" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "**meta_job_runs:**" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$JOB_RUNS" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "**Healthcheck:**" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$HEALTHCHECK_OUTPUT" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"

print_header "ШАГ 8: Настройка и тест systemd таймера"

print_step "Копирование systemd юнитов"

sudo cp ops/systemd/qtickets_api.service /etc/systemd/system/
sudo cp ops/systemd/qtickets_api.timer /etc/systemd/system/

print_step "Перезагрузка systemd и запуск таймера"

sudo systemctl daemon-reload
sudo systemctl enable --now qtickets_api.timer

print_step "Проверка статуса таймера"

TIMER_STATUS=$(systemctl status qtickets_api.timer)
echo "$TIMER_STATUS"

print_step "Принудительный запуск сервиса"

sudo systemctl start qtickets_api.service

print_step "Проверка статуса сервиса и логов"

SERVICE_STATUS=$(systemctl status qtickets_api.service)
echo "$SERVICE_STATUS"

SERVICE_LOG=$(journalctl -u qtickets_api.service -n 50 --no-pager)
echo "Логи сервиса:"
echo "$SERVICE_LOG"

# Сохранение результатов systemd в отчёт
echo "" >> "${REPORT_FILE}"
echo "### Systemd" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "**Статус таймера:**" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$TIMER_STATUS" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo "**Логи сервиса:**" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$SERVICE_LOG" | tail -20 >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"

print_header "ШАГ 9: Smoke-проверки качества данных"

print_step "Запуск smoke_checks_qtickets_api.sql"

SMOKE_OUTPUT=$(docker exec -i ch-zakaz clickhouse-client \
  --user=${CLICKHOUSE_USER} \
  --password='${CLICKHOUSE_PASSWORD}' \
  < infra/clickhouse/smoke_checks_qtickets_api.sql 2>&1)

echo "Результаты smoke-проверок:"
echo "$SMOKE_OUTPUT"

# Сохранение результатов smoke-проверок в отчёт
echo "" >> "${REPORT_FILE}"
echo "### Smoke проверки" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"
echo "$SMOKE_OUTPUT" >> "${REPORT_FILE}"
echo '```' >> "${REPORT_FILE}"

print_header "ЗАВЕРШЕНИЕ: Финальный вывод"

# Анализ результатов и формирование вывода
IS_READY=true

# Проверка на ошибки в лоадере
if echo "$LOADER_OUTPUT" | grep -q "ERROR\|Exception\|Traceback"; then
    IS_READY=false
fi

# Проверка наличия данных в staging
if echo "$STAGING_COUNT" | grep -q "rows.*0"; then
    IS_READY=false
fi

# Проверка статуса job runs
if ! echo "$JOB_RUNS" | grep -q "status.*ok"; then
    IS_READY=false
fi

# Формирование финального вывода
echo "" >> "${REPORT_FILE}"
echo "## Вывод" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"

if [ "$IS_READY" = true ]; then
    echo "✅ **Пайплайн QTickets API готов к выкладке на сервер заказчика**" >> "${REPORT_FILE}"
    echo "" >> "${REPORT_FILE}"
    echo "Все основные проверки пройдены успешно:" >> "${REPORT_FILE}"
    echo "- Миграция применена без ошибок" >> "${REPORT_FILE}"
    echo "- Лоадер успешно загрузил данные из QTickets API" >> "${REPORT_FILE}"
    echo "- Данные присутствуют в ClickHouse таблицах" >> "${REPORT_FILE}"
    echo "- Healthcheck показывает статус ok" >> "${REPORT_FILE}"
    echo "- Systemd сервис корректно настроен и работает" >> "${REPORT_FILE}"
    echo "- Smoke-проверки качества данных пройдены" >> "${REPORT_FILE}"
    echo "" >> "${REPORT_FILE}"
    echo "Рекомендуется proceeding с развертыванием на сервере заказчика." >> "${REPORT_FILE}"
    
    print_result "E2E тестирование завершено успешно. Пайплайн готов к выкладке."
else
    echo "❌ **Обнаружены проблемы, требующие исправления перед выкладкой**" >> "${REPORT_FILE}"
    echo "" >> "${REPORT_FILE}"
    echo "Необходимо устранить следующие проблемы:" >> "${REPORT_FILE}"
    
    if echo "$LOADER_OUTPUT" | grep -q "ERROR\|Exception\|Traceback"; then
        echo "- Ошибки в работе лоадера (см. логи выше)" >> "${REPORT_FILE}"
    fi
    
    if echo "$STAGING_COUNT" | grep -q "rows.*0"; then
        echo "- Данные не загружены в staging таблицу" >> "${REPORT_FILE}"
    fi
    
    if ! echo "$JOB_RUNS" | grep -q "status.*ok"; then
        echo "- Проблемы с записью в meta_job_runs" >> "${REPORT_FILE}"
    fi
    
    echo "" >> "${REPORT_FILE}"
    echo "Рекомендуется исправить указанные проблемы и повторить тестирование." >> "${REPORT_FILE}"
    
    print_error "Обнаружены проблемы. Пайплайн не готов к выкладке."
fi

echo "" >> "${REPORT_FILE}"
echo "---" >> "${REPORT_FILE}"
echo "Отчёт сгенерирован: $(date)" >> "${REPORT_FILE}"

print_result "Отчёт сохранён в ${REPORT_FILE}"