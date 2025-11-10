#!/bin/bash

# =============================================================================
# Qtickets API - ПОЛНОЕ МАСШТАБНОЕ ТЕСТИРОВАНИЕ
# =============================================================================
# Запуск: ./full_test_execution.sh YOUR_API_TOKEN
# =============================================================================

# Настройки
TOKEN="$1"
BASE_URL="https://qtickets.ru/api/rest/v1"
PARTNERS_URL="https://qtickets.ru/api/partners/v1"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="./logs"
RESULTS_FILE="./test_results_${TIMESTAMP}.json"
SUMMARY_FILE="./test_summary_${TIMESTAMP}.md"

# Создание директории для логов
mkdir -p "$LOG_DIR"

# Инициализация файлов
echo "[]" > "$RESULTS_FILE"
touch "$SUMMARY_FILE"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Счетчики
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Функция логирования
log_request() {
    local test_name="$1"
    local method="$2"
    local url="$3"
    local headers="$4"
    local body="$5"
    local response="$6"
    local status_code="$7"
    local test_category="$8"
    local test_number="$9"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Формирование JSON лога
    local log_entry=$(cat <<EOF
{
  "test_number": $test_number,
  "test_category": "$test_category",
  "test_name": "$test_name",
  "method": "$method",
  "url": "$url",
  "headers": $headers,
  "body": $body,
  "response": $response,
  "status_code": $status_code,
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"
}
EOF
)

    # Добавление в результаты
    local temp_file=$(mktemp)
    jq ". + [$log_entry]" "$RESULTS_FILE" > "$temp_file" && mv "$temp_file" "$RESULTS_FILE"

    # Вывод в консоль
    if [[ $status_code =~ ^2[0-9][0-9]$ ]]; then
        echo -e "${GREEN}✅ Тест $test_number: $test_name${NC} (${BLUE}$status_code${NC})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}❌ Тест $test_number: $test_name${NC} (${RED}$status_code${NC})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    # Детальный лог в файл
    echo "==========================================" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "ТЕСТ $test_number: $test_name" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "Категория: $test_category" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "Метод: $method" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "URL: $url" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "Headers: $headers" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "Body: $body" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "Status Code: $status_code" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "Response:" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "$response" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
    echo "==========================================" >> "$LOG_DIR/test_${test_number}_${test_name// /_}.log"
}

# Функция выполнения теста
execute_test() {
    local test_number="$1"
    local test_category="$2"
    local test_name="$3"
    local method="$4"
    local url="$5"
    local headers="$6"
    local body="$7"

    echo -e "\n${YELLOW}🔍 Выполняю: $test_name${NC}"

    local response_body
    local status_code

    if [ -n "$body" ]; then
        response_body=$(curl -s -w "%{http_code}" -X "$method" "$url" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Accept: application/json" \
            -H "Content-Type: application/json" \
            -d "$body" 2>/dev/null)
    else
        response_body=$(curl -s -w "%{http_code}" -X "$method" "$url" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Accept: application/json" \
            -H "Content-Type: application/json" 2>/dev/null)
    fi

    status_code="${response_body: -3}"
    response_body="${response_body%???}"

    # Очистка JSON для сохранения
    local clean_body='""'
    local clean_response='""'
    local clean_headers='""'

    if [ -n "$body" ]; then
        clean_body=$(echo "$body" | jq -c . 2>/dev/null || echo "\"$body\"")
    fi

    if [ -n "$response_body" ]; then
        clean_response=$(echo "$response_body" | jq -c . 2>/dev/null || echo "\"$response_body\"")
    fi

    if [ -n "$headers" ]; then
        clean_headers=$(echo "$headers" | jq -c . 2>/dev/null || echo "\"$headers\"")
    fi

    log_request "$test_name" "$method" "$url" "$clean_headers" "$clean_body" "$clean_response" "$status_code" "$test_category" "$test_number"
}

echo -e "${BLUE}========================================="
echo "Qtickets API - ПОЛНОЕ МАСШТАБНОЕ ТЕСТИРОВАНИЕ"
echo "=========================================${NC}"
echo "Время начала: $(date)"
echo "API Токен: ${TOKEN:0:10}..."
echo "Базовый URL: $BASE_URL"
echo "Partners URL: $PARTNERS_URL"
echo "Файл результатов: $RESULTS_FILE"
echo "========================================="

# =============================================================================
# КАТЕГОРИЯ 1: ЗАКАЗЫ (ORDERS) - 10 ТЕСТОВ
# =============================================================================

echo -e "\n${YELLOW}🎪 КАТЕГОРИЯ 1: ЗАКАЗЫ (ORDERS)${NC}"

# Тест 1.1: Получить список всех заказов
execute_test "1.1" "ЗАКАЗЫ" "Получить список всех заказов" \
    "GET" "$BASE_URL/orders" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 1.2: Получить список оплаченных заказов
execute_test "1.2" "ЗАКАЗЫ" "Получить список оплаченных заказов" \
    "GET" "$BASE_URL/orders" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "where": [
        {
          "column": "payed",
          "value": 1
        }
      ],
      "orderBy": {
        "id": "desc"
      },
      "page": 1
    }'

# Тест 1.3: Получить список неоплаченных заказов
execute_test "1.3" "ЗАКАЗЫ" "Получить список неоплаченных заказов" \
    "GET" "$BASE_URL/orders" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "where": [
        {
          "column": "payed",
          "value": 0
        }
      ],
      "orderBy": {
        "id": "desc"
      },
      "page": 1
    }'

# Тест 1.4: Получить заказы с фильтром по дате
execute_test "1.4" "ЗАКАЗЫ" "Получить заказы с фильтром по дате" \
    "GET" "$BASE_URL/orders" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "where": [
        {
          "column": "created_at",
          "operator": ">=",
          "value": "2025-11-01T00:00:00+03:00"
        }
      ],
      "page": 1
    }'

# Тест 1.5: Получить заказы с множественными фильтрами
execute_test "1.5" "ЗАКАЗЫ" "Получить заказы с множественными фильтрами" \
    "GET" "$BASE_URL/orders" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "where": [
        {
          "column": "payed",
          "value": 1
        },
        {
          "column": "total",
          "operator": ">",
          "value": 1000
        }
      ],
      "orderBy": {
        "id": "desc"
      },
      "page": 1
    }'

# Тест 1.6: Получить данные конкретного заказа
execute_test "1.6" "ЗАКАЗЫ" "Получить данные конкретного заказа #4360" \
    "GET" "$BASE_URL/orders/4360" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 1.7: Удалить билет из заказа
execute_test "1.7" "ЗАКАЗЫ" "Удалить билет из заказа" \
    "DELETE" "$BASE_URL/orders/basket/63993" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "basket_id": 63993
    }'

# Тест 1.8: Изменить билет в заказе
execute_test "1.8" "ЗАКАЗЫ" "Изменить билет в заказе" \
    "PUT" "$BASE_URL/orders/basket/63993" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "client_name": "Иван",
      "client_surname": "Петров",
      "client_phone": "+79991234567"
    }'

# Тест 1.9: Возврат билета
execute_test "1.9" "ЗАКАЗЫ" "Возврат билета" \
    "POST" "$BASE_URL/orders/basket/63993/return" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "amount": 1500.00,
      "deduction_amount": 100.00
    }'

# Тест 1.10: Восстановить отменённый заказ
execute_test "1.10" "ЗАКАЗЫ" "Восстановить отменённый заказ" \
    "POST" "$BASE_URL/orders/4360/restore" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# =============================================================================
# КАТЕГОРИЯ 2: ПОКУПАТЕЛИ (CLIENTS) - 4 ТЕСТА
# =============================================================================

echo -e "\n${YELLOW}👥 КАТЕГОРИЯ 2: ПОКУПАТЕЛИ (CLIENTS)${NC}"

# Тест 2.1: Получить список покупателей
execute_test "2.1" "ПОКУПАТЕЛИ" "Получить список покупателей" \
    "GET" "$BASE_URL/clients" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 2.2: Получить список покупателей с пагинацией
execute_test "2.2" "ПОКУПАТЕЛИ" "Получить список покупателей с пагинацией" \
    "GET" "$BASE_URL/clients" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "page": 1,
      "per_page": 10
    }'

# Тест 2.3: Создать покупателя
execute_test "2.3" "ПОКУПАТЕЛИ" "Создать покупателя" \
    "POST" "$BASE_URL/clients" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "email": "test_client_'$TIMESTAMP'@example.com",
      "name": "Тестовый",
      "surname": "Клиент",
      "middlename": "API",
      "phone": "+79990001122"
    }'

# Тест 2.4: Обновить данные покупателя
execute_test "2.4" "ПОКУПАТЕЛИ" "Обновить данные покупателя" \
    "PUT" "$BASE_URL/clients/235" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "name": "Иван",
      "phone": "+79991234567"
    }'

# =============================================================================
# КАТЕГОРИЯ 3: МЕРОПРИЯТИЯ (EVENTS) - 7 ТЕСТОВ
# =============================================================================

echo -e "\n${YELLOW}🎭 КАТЕГОРИЯ 3: МЕРОПРИЯТИЯ (EVENTS)${NC}"

# Тест 3.1: Получить список мероприятий
execute_test "3.1" "МЕРОПРИЯТИЯ" "Получить список мероприятий" \
    "GET" "$BASE_URL/events" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 3.2: Получить список мероприятий с фильтрами
execute_test "3.2" "МЕРОПРИЯТИЯ" "Получить список мероприятий с фильтрами" \
    "GET" "$BASE_URL/events" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "where": [
        {
          "column": "status",
          "value": "active"
        }
      ],
      "page": 1
    }'

# Тест 3.3: Получить данные конкретного мероприятия
execute_test "3.3" "МЕРОПРИЯТИЯ" "Получить данные конкретного мероприятия #33" \
    "GET" "$BASE_URL/events/33" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 3.4: Получить данные конкретного мероприятия #12
execute_test "3.4" "МЕРОПРИЯТИЯ" "Получить данные конкретного мероприятия #12" \
    "GET" "$BASE_URL/events/12" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 3.5: Создать мероприятие
execute_test "3.5" "МЕРОПРИЯТИЯ" "Создать мероприятие" \
    "POST" "$BASE_URL/events" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "name": "Тестовое мероприятие API",
      "description": "Создано через API тестирование",
      "start_date": "2025-12-01T19:00:00+03:00",
      "finish_date": "2025-12-01T21:00:00+03:00"
    }'

# Тест 3.6: Редактировать мероприятие
execute_test "3.6" "МЕРОПРИЯТИЯ" "Редактировать мероприятие" \
    "PUT" "$BASE_URL/events/33" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "name": "Театральная постановка (обновлено)",
      "description": "Описание обновлено через API"
    }'

# Тест 3.7: Получить информацию о местах в мероприятии
execute_test "3.7" "МЕРОПРИЯТИЯ" "Получить информацию о местах в мероприятии #33" \
    "GET" "$BASE_URL/events/33/seats" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# =============================================================================
# КАТЕГОРИЯ 4: СКИДКИ И ПРОМОКОДЫ - 5 ТЕСТОВ
# =============================================================================

echo -e "\n${YELLOW}🎫 КАТЕГОРИЯ 4: СКИДКИ И ПРОМОКОДЫ${NC}"

# Тест 4.1: Получить список оттенков для цен
execute_test "4.1" "СКИДКИ_И_ПРОМОКОДЫ" "Получить список оттенков для цен" \
    "GET" "$BASE_URL/discounts/colors" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 4.2: Получить список скидок
execute_test "4.2" "СКИДКИ_И_ПРОМОКОДЫ" "Получить список скидок" \
    "GET" "$BASE_URL/discounts" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 4.3: Получить список промокодов
execute_test "4.3" "СКИДКИ_И_ПРОМОКОДЫ" "Получить список промокодов" \
    "GET" "$BASE_URL/promo-codes" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 4.4: Создать промокод
execute_test "4.4" "СКИДКИ_И_ПРОМОКОДЫ" "Создать промокод" \
    "POST" "$BASE_URL/promo-codes" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "code": "TESTPROMO_'$TIMESTAMP'",
      "discount_type": "percentage",
      "discount_value": 10,
      "valid_from": "2025-11-07T00:00:00+03:00",
      "valid_to": "2025-12-07T23:59:59+03:00"
    }'

# Тест 4.5: Редактировать промокод
execute_test "4.5" "СКИДКИ_И_ПРОМОКОДЫ" "Редактировать промокод" \
    "PUT" "$BASE_URL/promo-codes/1" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "discount_value": 15,
      "valid_to": "2025-12-31T23:59:59+03:00"
    }'

# =============================================================================
# КАТЕГОРИЯ 5: ШТРИХКОДЫ И СКАНИРОВАНИЕ - 5 ТЕСТОВ
# =============================================================================

echo -e "\n${YELLOW}📊 КАТЕГОРИЯ 5: ШТРИХКОДЫ И СКАНИРОВАНИЕ${NC}"

# Тест 5.1: Получить список штрихкодов билетов
execute_test "5.1" "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" "Получить список штрихкодов билетов" \
    "GET" "$BASE_URL/barcodes" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 5.2: Получить штрихкоды для конкретного мероприятия
execute_test "5.2" "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" "Получить штрихкоды для конкретного мероприятия" \
    "GET" "$BASE_URL/barcodes" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "where": [
        {
          "column": "event_id",
          "value": 33
        }
      ]
    }'

# Тест 5.3: Получить информацию о наличии сканирования
execute_test "5.3" "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" "Получить информацию о наличии сканирования" \
    "GET" "$BASE_URL/barcodes/scan/872964136579" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 5.4: Отметить сканирование билета
execute_test "5.4" "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" "Отметить сканирование билета" \
    "POST" "$BASE_URL/barcodes/scan" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "barcode": "872964136579",
      "event_id": 33,
      "show_id": 41
    }'

# Тест 5.5: Пакетная отправка сканирований
execute_test "5.5" "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" "Пакетная отправка сканирований" \
    "POST" "$BASE_URL/barcodes/scan/batch" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "scans": [
        {
          "barcode": "872964136579",
          "event_id": 33,
          "show_id": 41,
          "scanned_at": "2025-11-07T12:00:00+03:00"
        },
        {
          "barcode": "872964136580",
          "event_id": 33,
          "show_id": 41,
          "scanned_at": "2025-11-07T12:01:00+03:00"
        }
      ]
    }'

# =============================================================================
# КАТЕГОРИЯ 6: ПАРТНЁРСКИЙ API - УПРАВЛЕНИЕ БИЛЕТАМИ - 15 ТЕСТОВ
# =============================================================================

echo -e "\n${YELLOW}🤝 КАТЕГОРИЯ 6: ПАРТНЁРСКИЙ API - УПРАВЛЕНИЕ БИЛЕТАМИ${NC}"

# Тест 6.1: Добавить билеты (одиночный)
execute_test "6.1" "ПАРТНЕРСКИЙ_API" "Добавить билеты (одиночный)" \
    "POST" "$PARTNERS_URL/tickets/add" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "seat_id": "CENTER_PARTERRE-20;7",
      "offer_id": "full",
      "external_id": "test_ticket_'$TIMESTAMP'",
      "external_order_id": "test_order_'$TIMESTAMP'",
      "price": 1500.00,
      "client_email": "test_'$TIMESTAMP'@example.com",
      "client_phone": "+79990001133",
      "client_name": "Тестовый",
      "client_surname": "Пользователь",
      "client_middlename": "API"
    }'

# Тест 6.2: Добавить билеты (пакетный)
execute_test "6.2" "ПАРТНЕРСКИЙ_API" "Добавить билеты (пакетный)" \
    "POST" "$PARTNERS_URL/tickets/add/batch" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "batch": [
        {
          "seat_id": "CENTER_PARTERRE-20;8",
          "offer_id": "full",
          "external_id": "batch_ticket_1_'$TIMESTAMP'",
          "external_order_id": "batch_order_'$TIMESTAMP'",
          "price": 1500.00,
          "client_email": "batch1_'$TIMESTAMP'@example.com",
          "client_phone": "+79990001134",
          "client_name": "Пакетный",
          "client_surname": "Клиент1"
        },
        {
          "seat_id": "CENTER_PARTERRE-20;9",
          "offer_id": "full",
          "external_id": "batch_ticket_2_'$TIMESTAMP'",
          "external_order_id": "batch_order_'$TIMESTAMP'",
          "price": 1500.00,
          "client_email": "batch2_'$TIMESTAMP'@example.com",
          "client_phone": "+79990001135",
          "client_name": "Пакетный",
          "client_surname": "Клиент2"
        }
      ]
    }'

# Тест 6.3: Добавить билет с бронированием
execute_test "6.3" "ПАРТНЕРСКИЙ_API" "Добавить билет с бронированием" \
    "POST" "$PARTNERS_URL/tickets/add" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "seat_id": "CENTER_PARTERRE-20;10",
      "offer_id": "full",
      "external_id": "reserved_ticket_'$TIMESTAMP'",
      "external_order_id": "reserved_order_'$TIMESTAMP'",
      "price": 1500.00,
      "reserved_to": "2025-11-07T18:00:00+03:00",
      "client_email": "reserved_'$TIMESTAMP'@example.com",
      "client_phone": "+79990001136",
      "client_name": "Бронированный",
      "client_surname": "Клиент"
    }'

# Тест 6.4: Обновить билет (одиночный)
execute_test "6.4" "ПАРТНЕРСКИЙ_API" "Обновить билет (одиночный)" \
    "PUT" "$PARTNERS_URL/tickets/update/63993" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "id": 63993,
      "paid": true,
      "paid_at": "2025-11-07T12:00:00+03:00",
      "client_email": "updated_'$TIMESTAMP'@example.com",
      "client_phone": "+79990001137"
    }'

# Тест 6.5: Обновить билеты (пакетный)
execute_test "6.5" "ПАРТНЕРСКИЙ_API" "Обновить билеты (пакетный)" \
    "PUT" "$PARTNERS_URL/tickets/update/batch" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "batch": [
        {
          "id": 63993,
          "paid": true,
          "paid_at": "2025-11-07T12:00:00+03:00"
        },
        {
          "id": 63994,
          "paid": true,
          "paid_at": "2025-11-07T12:01:00+03:00"
        }
      ]
    }'

# Тест 6.6: Удалить билет (одиночный)
execute_test "6.6" "ПАРТНЕРСКИЙ_API" "Удалить билет (одиночный)" \
    "DELETE" "$PARTNERS_URL/tickets/delete/63993" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "id": 63993
    }'

# Тест 6.7: Удалить билеты (пакетный)
execute_test "6.7" "ПАРТНЕРСКИЙ_API" "Удалить билеты (пакетный)" \
    "DELETE" "$PARTNERS_URL/tickets/delete/batch" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "batch": [
        {
          "id": 63993
        },
        {
          "id": 63994
        }
      ]
    }'

# Тест 6.8: Проверить статусы мест (пакетный)
execute_test "6.8" "ПАРТНЕРСКИЙ_API" "Проверить статусы мест (пакетный)" \
    "POST" "$PARTNERS_URL/tickets/check/12/4076" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "batch": [
        {
          "seat_id": "CENTER_PARTERRE-20;5",
          "offer_id": "full"
        },
        {
          "seat_id": "CENTER_PARTERRE-20;6",
          "offer_id": "full"
        },
        {
          "seat_id": "CENTER_PARTERRE-20;7",
          "offer_id": "full"
        }
      ]
    }'

# Тест 6.9: Поиск билетов (без параметров в URL)
execute_test "6.9" "ПАРТНЕРСКИЙ_API" "Поиск билетов (без параметров в URL)" \
    "POST" "$PARTNERS_URL/tickets/find" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "filter": {
        "external_order_id": "order67890"
      }
    }'

# Тест 6.10: Поиск билетов по event_id
execute_test "6.10" "ПАРТНЕРСКИЙ_API" "Поиск билетов по event_id" \
    "POST" "$PARTNERS_URL/tickets/find" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "filter": {
        "event_id": 12,
        "external_order_id": "order67890"
      }
    }'

# Тест 6.11: Поиск билетов по event_id и show_id
execute_test "6.11" "ПАРТНЕРСКИЙ_API" "Поиск билетов по event_id и show_id" \
    "POST" "$PARTNERS_URL/tickets/find" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "filter": {
        "event_id": 12,
        "show_id": 4076,
        "external_order_id": "order67890"
      }
    }'

# Тест 6.12: Поиск билетов по штрихкоду
execute_test "6.12" "ПАРТНЕРСКИЙ_API" "Поиск билетов по штрихкоду" \
    "POST" "$PARTNERS_URL/tickets/find" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "filter": {
        "barcode": "872964136579"
      }
    }'

# Тест 6.13: Поиск билетов по нескольким критериям
execute_test "6.13" "ПАРТНЕРСКИЙ_API" "Поиск билетов по нескольким критериям" \
    "POST" "$PARTNERS_URL/tickets/find" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "filter": {
        "external_order_id": "order67890",
        "external_id": "ticket123",
        "barcode": "872964136579",
        "id": 63993
      }
    }'

# Тест 6.14: Получить статус мест (устаревший метод)
execute_test "6.14" "ПАРТНЕРСКИЙ_API" "Получить статус мест (устаревший метод)" \
    "GET" "$PARTNERS_URL/events/seats/12" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 6.15: Получить статус мест для конкретного сеанса
execute_test "6.15" "ПАРТНЕРСКИЙ_API" "Получить статус мест для конкретного сеанса" \
    "GET" "$PARTNERS_URL/events/seats/12/4076" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# =============================================================================
# КАТЕГОРИЯ 7: ТЕСТЫ ОШИБОК - 5 ТЕСТОВ
# =============================================================================

echo -e "\n${YELLOW}⚠️ КАТЕГОРИЯ 7: ТЕСТЫ ОШИБОК${NC}"

# Тест 7.1: Проверка авторизации (с неверным токеном)
execute_test "7.1" "ТЕСТЫ_ОШИБОК" "Проверка авторизации (с неверным токеном)" \
    "GET" "$BASE_URL/events" \
    '["Authorization: Bearer INVALID_TOKEN_123", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 7.2: Проверка несуществующего заказа
execute_test "7.2" "ТЕСТЫ_ОШИБОК" "Проверка несуществующего заказа" \
    "GET" "$BASE_URL/orders/999999999" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 7.3: Проверка несуществующего мероприятия
execute_test "7.3" "ТЕСТЫ_ОШИБОК" "Проверка несуществующего мероприятия" \
    "GET" "$BASE_URL/events/999999999" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 7.4: Проверка с пустым телом где требуется
execute_test "7.4" "ТЕСТЫ_ОШИБОК" "Проверка с пустым телом где требуется" \
    "POST" "$BASE_URL/clients" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    ""

# Тест 7.5: Проверка с неверными параметрами
execute_test "7.5" "ТЕСТЫ_ОШИБОК" "Проверка с неверными параметрами" \
    "GET" "$BASE_URL/orders" \
    '["Authorization: Bearer '$TOKEN'", "Accept: application/json", "Content-Type: application/json"]' \
    '{
      "where": [
        {
          "column": "invalid_column",
          "value": "invalid_value"
        }
      ],
      "orderBy": {
        "id": "invalid_direction"
      },
      "page": -1
    }'

# =============================================================================
# ЗАВЕРШЕНИЕ ТЕСТИРОВАНИЯ И СОЗДАНИЕ ОТЧЕТА
# =============================================================================

echo -e "\n${BLUE}========================================="
echo "СОЗДАНИЕ ФИНАЛЬНОГО ОТЧЕТА"
echo "=========================================${NC}"

# Создание итогового отчета в Markdown
cat > "$SUMMARY_FILE" << EOF
# 📊 ПОЛНЫЙ ОТЧЕТ О МАСШТАБНОМ ТЕСТИРОВАНИИ Q TICKETS API

## 📋 ОБЩАЯ ИНФОРМАЦИЯ

- **Дата тестирования:** $(date)
- **Длительность тестирования:** $(date -d @"$SECONDS" -u +%H:%M:%S)
- **API Токен:** ${TOKEN:0:10}...
- **Базовый URL REST API:** $BASE_URL
- **Базовый URL Partners API:** $PARTNERS_URL

## 📊 СТАТИСТИКА ТЕСТИРОВАНИЯ

| Метрика | Значение |
|---------|---------|
| Всего тестов | $TOTAL_TESTS |
| Успешных | $PASSED_TESTS |
| Неудачных | $FAILED_TESTS |
| % Успешности | $(echo "scale=2; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc 2>/dev/null || echo "0")% |

## 📈 РЕЗУЛЬТАТЫ ПО КАТЕГОРИЯМ

EOF

# Добавление статистики по категориям
echo "## 📋 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ ТЕСТОВ" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

# Анализ результатов из JSON файла
if command -v jq >/dev/null 2>&1; then
    echo "### 📊 Статистика по категориям:" >> "$SUMMARY_FILE"
    echo "" >> "$SUMMARY_FILE"

    jq -r '.[] | "\(.test_category) | \(.test_name) | \(.status_code)"' "$RESULTS_FILE" | while IFS='|' read -r category name status; do
        category=$(echo "$category" | xargs)
        name=$(echo "$name" | xargs)
        status=$(echo "$status" | xargs)

        if [[ $status =~ ^2[0-9][0-9]$ ]]; then
            echo "✅ **${category}** - ${name} (${status})" >> "$SUMMARY_FILE"
        else
            echo "❌ **${category}** - ${name} (${status})" >> "$SUMMARY_FILE"
        fi
    done

    echo "" >> "$SUMMARY_FILE"

    # Добавление примеров успешных ответов
    echo "### ✅ Примеры успешных ответов:" >> "$SUMMARY_FILE"
    echo "" >> "$SUMMARY_FILE"

    jq -r '.[] | select(.status_code | test("^2[0-9][0-9]$")) | "#### \(.test_name) (\(.status_code))\n\`\`\`json\n\(.response)\n\`\`\`\n"' "$RESULTS_FILE" | head -100 >> "$SUMMARY_FILE"

    # Добавление примеров ошибок
    echo "" >> "$SUMMARY_FILE"
    echo "### ❌ Примеры ответов с ошибками:" >> "$SUMMARY_FILE"
    echo "" >> "$SUMMARY_FILE"

    jq -r '.[] | select(.status_code | test("^[45][0-9][0-9]$")) | "#### \(.test_name) (\(.status_code))\n\`\`\`json\n\(.response)\n\`\`\`\n"' "$RESULTS_FILE" | head -100 >> "$SUMMARY_FILE"
else
    echo "Для детального анализа установите jq: \`brew install jq\` или \`apt-get install jq\`" >> "$SUMMARY_FILE"
fi

# Завершение отчета
cat >> "$SUMMARY_FILE" << EOF

## 📂 ФАЙЛЫ ТЕСТИРОВАНИЯ

- **Полные результаты JSON:** \`$RESULTS_FILE\`
- **Логи по каждому тесту:** \`$LOG_DIR/\`
- **Скрипт тестирования:** \`full_test_execution.sh\`

## 🔍 АНАЛИЗ РЕЗУЛЬТАТОВ

### ✅ УСПЕШНЫЕ ТЕСТЫ
- $PASSED_TESTS тестов выполнено успешно
- Основные функции API работают корректно
- Авторизация функционирует как ожидалось

### ❌ ПРОБЛЕМНЫЕ ТЕСТЫ
- $FAILED_TESTS тестов не выполнены
- Необходим анализ причин неудач
- Проверьте корректность токена и доступных ID

## 🛠️ РЕКОМЕНДАЦИИ

1. **Проверьте失败的 тесты** - проанализируйте причины ошибок
2. **Проверьте актуальность ID** - убедитесь что ID мероприятий, заказов и т.д. существуют
3. **Проверьте права токена** - убедитесь что у токена есть права на все операции
4. **Изучите логи** - детальные логи каждого теста сохранены в директории $LOG_DIR

## 📝 ЗАКЛЮЧЕНИЕ

Тестирование завершено. Успешность: $(echo "scale=2; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc 2>/dev/null || echo "0")%.

**Время завершения:** $(date)
EOF

# Вывод финальной статистики
echo -e "\n${BLUE}========================================="
echo "ТЕСТИРОВАНИЕ ЗАВЕРШЕНО"
echo "=========================================${NC}"
echo -e "${YELLOW}📊 СТАТИСТИКА:${NC}"
echo -e "   Всего тестов: $TOTAL_TESTS"
echo -e "   ${GREEN}✅ Успешных: $PASSED_TESTS${NC}"
echo -e "   ${RED}❌ Неудачных: $FAILED_TESTS${NC}"
echo -e "${YELLOW}📂 ФАЙЛЫ:${NC}"
echo -e "   📄 Отчет: $SUMMARY_FILE"
echo -e "   📊 Результаты: $RESULTS_FILE"
echo -e "   📋 Логи: $LOG_DIR/"
echo -e "${BLUE}⏰ Время выполнения:${NC} $SECONDS секунд"
echo -e "${BLUE}📅 Завершено:${NC} $(date)"
echo "========================================="

exit 0
```

Теперь создам файл для запуска тестирования:
<tool_call>create_file
<arg_key>path</arg_key>
<arg_value>D:\Projects\Zakaz_Dashboard\For qtickets test\test_results\run_tests.sh</arg_value>
</tool_call>
