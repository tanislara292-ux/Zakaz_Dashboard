#!/bin/bash
# Qtickets API - Готовые CURL команды для тестирования
# Замените YOUR_TOKEN на ваш реальный токен

# ВАЖНО: Установите ваш токен здесь
TOKEN="YOUR_TOKEN"

echo "========================================="
echo "Qtickets API - Тестирование"
echo "========================================="

# ============================================
# 1. ЗАКАЗЫ
# ============================================

echo ""
echo "1. Получить список всех заказов..."
curl -X GET "https://qtickets.ru/api/rest/v1/orders" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

echo ""
echo ""
echo "2. Получить список оплаченных заказов..."
curl -X GET "https://qtickets.ru/api/rest/v1/orders" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
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

echo ""
echo ""
echo "3. Получить данные заказа #4360..."
curl -X GET "https://qtickets.ru/api/rest/v1/orders/4360" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

# ============================================
# 2. МЕРОПРИЯТИЯ
# ============================================

echo ""
echo ""
echo "4. Получить список мероприятий..."
curl -X GET "https://qtickets.ru/api/rest/v1/events" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

echo ""
echo ""
echo "5. Получить данные мероприятия #33..."
curl -X GET "https://qtickets.ru/api/rest/v1/events/33" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

echo ""
echo ""
echo "6. Получить информацию о местах мероприятия #33..."
curl -X GET "https://qtickets.ru/api/rest/v1/events/33/seats" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

# ============================================
# 3. ПОКУПАТЕЛИ
# ============================================

echo ""
echo ""
echo "7. Получить список покупателей..."
curl -X GET "https://qtickets.ru/api/rest/v1/clients" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

# ============================================
# 4. ПРОМОКОДЫ И СКИДКИ
# ============================================

echo ""
echo ""
echo "8. Получить список промокодов..."
curl -X GET "https://qtickets.ru/api/rest/v1/promo-codes" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

echo ""
echo ""
echo "9. Получить список скидок..."
curl -X GET "https://qtickets.ru/api/rest/v1/discounts" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

# ============================================
# 5. ШТРИХКОДЫ
# ============================================

echo ""
echo ""
echo "10. Получить список штрихкодов..."
curl -X GET "https://qtickets.ru/api/rest/v1/barcodes" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

# ============================================
# 6. ПАРТНЁРСКИЙ API - БИЛЕТЫ
# ============================================

echo ""
echo ""
echo "11. Поиск билетов по external_order_id..."
curl -X POST "https://qtickets.ru/api/partners/v1/tickets/find" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "filter": {
      "external_order_id": "order67890"
    }
  }'

echo ""
echo ""
echo "12. Поиск билетов по штрихкоду..."
curl -X POST "https://qtickets.ru/api/partners/v1/tickets/find" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "filter": {
      "barcode": "872964136579"
    }
  }'

echo ""
echo ""
echo "13. Проверка статуса мест для event #12, show #4076..."
curl -X POST "https://qtickets.ru/api/partners/v1/tickets/check/12/4076" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "batch": [
      {
        "seat_id": "CENTER_PARTERRE-20;5",
        "offer_id": "full"
      },
      {
        "seat_id": "CENTER_PARTERRE-20;6",
        "offer_id": "full"
      }
    ]
  }'

echo ""
echo ""
echo "14. Получить статус мест (старый метод) для event #12..."
curl -X GET "https://qtickets.ru/api/partners/v1/events/seats/12" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

# ============================================
# 7. ТЕСТЫ ОШИБОК
# ============================================

echo ""
echo ""
echo "15. Тест неверной авторизации..."
curl -X GET "https://qtickets.ru/api/rest/v1/events" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer INVALID_TOKEN_123"

echo ""
echo ""
echo "16. Тест несуществующего заказа..."
curl -X GET "https://qtickets.ru/api/rest/v1/orders/999999999" \
  -H "Accept: application/json" \
  -H "Cache-Control: no-cache" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

echo ""
echo ""
echo "========================================="
echo "Тестирование завершено!"
echo "========================================="
