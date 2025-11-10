# Qtickets API - Полный набор тестовых запросов

**Base URL:** `https://qtickets.ru/api/rest/v1/`
**Base URL (Partners API):** `https://qtickets.ru/api/partners/v1/`

**Заголовки для всех запросов:**
```
Accept: application/json
Cache-Control: no-cache
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN
```

---

## 1. ЗАКАЗЫ (ORDERS)

### 1.1. Получить список заказов (без фильтров)
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/orders
```
**Body:** нет

---

### 1.2. Получить список заказов с фильтром (оплаченные)
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/orders
```
**Body:**
```json
{
  "where": [
    {
      "column": "payed",
      "value": 1
    }
  ],
  "orderBy": {
    "id": "asc"
  },
  "page": 1
}
```

---

### 1.3. Получить список заказов с фильтром (неоплаченные)
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/orders
```
**Body:**
```json
{
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
}
```

---

### 1.4. Получить список заказов с фильтром по дате
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/orders
```
**Body:**
```json
{
  "where": [
    {
      "column": "created_at",
      "operator": ">=",
      "value": "2025-01-01"
    }
  ],
  "page": 1
}
```

---

### 1.5. Получить список заказов с множественными фильтрами
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/orders
```
**Body:**
```json
{
  "where": [
    {
      "column": "payed",
      "value": 1
    },
    {
      "column": "event_id",
      "value": 33
    }
  ],
  "orderBy": {
    "id": "desc"
  },
  "page": 1
}
```

---

### 1.6. Получить данные конкретного заказа
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/orders/{ORDER_ID}
```
**Примеры:**
- `GET https://qtickets.ru/api/rest/v1/orders/4360`
- `GET https://qtickets.ru/api/rest/v1/orders/1`
- `GET https://qtickets.ru/api/rest/v1/orders/12345`

---

### 1.7. Удалить билет из заказа
**Запрос:**
```
DELETE https://qtickets.ru/api/rest/v1/orders/{ORDER_ID}/baskets/{BASKET_ID}
```
**Примеры:**
- `DELETE https://qtickets.ru/api/rest/v1/orders/4360/baskets/63993`

---

### 1.8. Изменить билет в заказе
**Запрос:**
```
PATCH https://qtickets.ru/api/rest/v1/orders/{ORDER_ID}/baskets/{BASKET_ID}
```
**Body:**
```json
{
  "client_name": "Новое Имя",
  "client_surname": "Новая Фамилия",
  "client_phone": "+79991234567"
}
```
**Примеры:**
- `PATCH https://qtickets.ru/api/rest/v1/orders/4360/baskets/63993`

---

### 1.9. Возврат билета
**Запрос:**
```
POST https://qtickets.ru/api/rest/v1/orders/{ORDER_ID}/baskets/{BASKET_ID}/refund
```
**Body:**
```json
{
  "amount": 150,
  "deduction_amount": 15
}
```
**Примеры:**
- `POST https://qtickets.ru/api/rest/v1/orders/4360/baskets/63993/refund`

---

### 1.10. Восстановить отменённый заказ
**Запрос:**
```
POST https://qtickets.ru/api/rest/v1/orders/{ORDER_ID}/restore
```
**Примеры:**
- `POST https://qtickets.ru/api/rest/v1/orders/4360/restore`

---

## 2. ПОКУПАТЕЛИ (CLIENTS)

### 2.1. Получить список покупателей
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/clients
```
**Body:** нет

---

### 2.2. Получить список покупателей с пагинацией
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/clients
```
**Body:**
```json
{
  "page": 1,
  "per_page": 50
}
```

---

### 2.3. Создать покупателя
**Запрос:**
```
POST https://qtickets.ru/api/rest/v1/clients
```
**Body:**
```json
{
  "email": "test@example.com",
  "name": "Тестовый",
  "surname": "Покупатель",
  "middlename": "Тестович",
  "phone": "+79001234567"
}
```

---

### 2.4. Обновить данные покупателя
**Запрос:**
```
PATCH https://qtickets.ru/api/rest/v1/clients/{CLIENT_ID}
```
**Body:**
```json
{
  "name": "Обновлённое Имя",
  "phone": "+79009876543"
}
```
**Примеры:**
- `PATCH https://qtickets.ru/api/rest/v1/clients/235`

---

## 3. МЕРОПРИЯТИЯ (EVENTS)

### 3.1. Получить список мероприятий
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/events
```
**Body:** нет

---

### 3.2. Получить список мероприятий с фильтрами
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/events
```
**Body:**
```json
{
  "where": [
    {
      "column": "active",
      "value": 1
    }
  ],
  "page": 1
}
```

---

### 3.3. Получить данные конкретного мероприятия
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/events/{EVENT_ID}
```
**Примеры:**
- `GET https://qtickets.ru/api/rest/v1/events/33`
- `GET https://qtickets.ru/api/rest/v1/events/12`

---

### 3.4. Создать мероприятие
**Запрос:**
```
POST https://qtickets.ru/api/rest/v1/events
```
**Body:**
```json
{
  "name": "Тестовое мероприятие",
  "description": "Описание мероприятия",
  "start_date": "2025-12-01T19:00:00+03:00",
  "finish_date": "2025-12-01T22:00:00+03:00"
}
```

---

### 3.5. Редактировать мероприятие
**Запрос:**
```
PATCH https://qtickets.ru/api/rest/v1/events/{EVENT_ID}
```
**Body:**
```json
{
  "name": "Обновлённое название",
  "description": "Новое описание"
}
```
**Примеры:**
- `PATCH https://qtickets.ru/api/rest/v1/events/33`

---

### 3.6. Получить информацию о местах в мероприятии
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/events/{EVENT_ID}/seats
```
**Примеры:**
- `GET https://qtickets.ru/api/rest/v1/events/33/seats`

---

### 3.7. Получить информацию о местах в конкретном сеансе
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/events/{EVENT_ID}/seats/{SHOW_ID}
```
**Примеры:**
- `GET https://qtickets.ru/api/rest/v1/events/33/seats/41`

---

## 4. СКИДКИ И ПРОМОКОДЫ

### 4.1. Получить список оттенков для цен
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/price-shades
```

---

### 4.2. Получить список скидок
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/discounts
```

---

### 4.3. Получить список промокодов
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/promo-codes
```

---

### 4.4. Создать промокод
**Запрос:**
```
POST https://qtickets.ru/api/rest/v1/promo-codes
```
**Body:**
```json
{
  "code": "TESTPROMO2025",
  "discount_type": "percent",
  "discount_value": 10,
  "valid_from": "2025-01-01",
  "valid_to": "2025-12-31"
}
```

---

### 4.5. Редактировать промокод
**Запрос:**
```
PATCH https://qtickets.ru/api/rest/v1/promo-codes/{PROMO_CODE_ID}
```
**Body:**
```json
{
  "discount_value": 15,
  "valid_to": "2026-01-31"
}
```

---

## 5. ШТРИХКОДЫ И СКАНИРОВАНИЕ

### 5.1. Получить список штрихкодов билетов
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/barcodes
```

---

### 5.2. Получить штрихкоды для конкретного мероприятия
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/barcodes
```
**Body:**
```json
{
  "where": [
    {
      "column": "event_id",
      "value": 33
    }
  ]
}
```

---

### 5.3. Получить информацию о наличии сканирования
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/scanning/info
```

---

### 5.4. Отметить сканирование билета
**Запрос:**
```
POST https://qtickets.ru/api/rest/v1/scanning/scan
```
**Body:**
```json
{
  "barcode": "877076325904",
  "event_id": 33,
  "show_id": 41
}
```

---

### 5.5. Пакетная отправка сканирований
**Запрос:**
```
POST https://qtickets.ru/api/rest/v1/scanning/batch
```
**Body:**
```json
{
  "scans": [
    {
      "barcode": "877076325904",
      "event_id": 33,
      "show_id": 41,
      "scanned_at": "2025-11-07T19:30:00+03:00"
    },
    {
      "barcode": "877344688530",
      "event_id": 33,
      "show_id": 41,
      "scanned_at": "2025-11-07T19:31:00+03:00"
    }
  ]
}
```

---

## 6. ПАРТНЁРСКИЙ API - УПРАВЛЕНИЕ БИЛЕТАМИ

### 6.1. Добавить билеты (одиночный)
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/add/{EVENT_ID}/{SHOW_ID}
```
**Body:**
```json
{
  "seat_id": "CENTER_PARTERRE-20;5",
  "offer_id": "full",
  "external_id": "ticket12345",
  "external_order_id": "order67890",
  "price": 1500.50,
  "client_email": "test@example.com",
  "client_phone": "+79001234567",
  "client_name": "Тест",
  "client_surname": "Тестов",
  "client_middlename": "Тестович"
}
```
**Примеры:**
- `POST https://qtickets.ru/api/partners/v1/tickets/add/12/4076`

---

### 6.2. Добавить билеты (пакетный)
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/add/{EVENT_ID}/{SHOW_ID}
```
**Body:**
```json
{
  "batch": [
    {
      "seat_id": "CENTER_PARTERRE-20;5",
      "offer_id": "full",
      "external_id": "ticket001",
      "external_order_id": "order123",
      "price": 1500.50,
      "client_email": "user1@example.com",
      "client_phone": "+79001234567",
      "client_name": "Иван",
      "client_surname": "Иванов"
    },
    {
      "seat_id": "CENTER_PARTERRE-20;6",
      "offer_id": "full",
      "external_id": "ticket002",
      "external_order_id": "order123",
      "price": 1500.50,
      "client_email": "user1@example.com",
      "client_phone": "+79001234567",
      "client_name": "Иван",
      "client_surname": "Иванов"
    }
  ]
}
```

---

### 6.3. Добавить билет с бронированием
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/add/{EVENT_ID}/{SHOW_ID}
```
**Body:**
```json
{
  "seat_id": "CENTER_PARTERRE-20;5",
  "offer_id": "full",
  "external_id": "ticket12345",
  "external_order_id": "order67890",
  "price": 1500.50,
  "reserved_to": "2025-11-08T19:00:00+03:00",
  "client_email": "test@example.com",
  "client_phone": "+79001234567",
  "client_name": "Тест",
  "client_surname": "Тестов"
}
```

---

### 6.4. Обновить билет (одиночный)
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/update/{EVENT_ID}/{SHOW_ID}
```
**Body:**
```json
{
  "id": 120260,
  "paid": 1,
  "paid_at": "2025-11-07T15:30:00+03:00",
  "client_email": "updated@example.com",
  "client_phone": "+79009999999"
}
```
**Примеры:**
- `POST https://qtickets.ru/api/partners/v1/tickets/update/12/4076`

---

### 6.5. Обновить билеты (пакетный)
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/update/{EVENT_ID}/{SHOW_ID}
```
**Body:**
```json
{
  "batch": [
    {
      "id": 120260,
      "paid": 1,
      "paid_at": "2025-11-07T15:30:00+03:00"
    },
    {
      "id": 120261,
      "paid": 1,
      "paid_at": "2025-11-07T15:30:00+03:00"
    }
  ]
}
```

---

### 6.6. Удалить билет (одиночный)
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/remove/{EVENT_ID}/{SHOW_ID}
```
**Body:**
```json
{
  "id": 120260
}
```

---

### 6.7. Удалить билеты (пакетный)
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/remove/{EVENT_ID}/{SHOW_ID}
```
**Body:**
```json
{
  "batch": [
    {
      "id": 120260
    },
    {
      "id": 120261
    }
  ]
}
```

---

### 6.8. Проверить статусы мест (пакетный)
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/check/{EVENT_ID}/{SHOW_ID}
```
**Body:**
```json
{
  "batch": [
    {
      "seat_id": "CENTER_PARTERRE-20;5",
      "offer_id": "preferential"
    },
    {
      "seat_id": "CENTER_PARTERRE-20;5",
      "offer_id": "full"
    },
    {
      "seat_id": "CENTER_PARTERRE-20;6",
      "offer_id": "full"
    }
  ]
}
```

---

### 6.9. Поиск билетов (без параметров в URL)
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/find
```
**Body:**
```json
{
  "filter": {
    "external_order_id": "order67890"
  }
}
```

---

### 6.10. Поиск билетов по event_id
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/find/12
```
**Body:**
```json
{
  "filter": {
    "external_order_id": "order67890"
  }
}
```

---

### 6.11. Поиск билетов по event_id и show_id
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/find/12/4076
```
**Body:**
```json
{
  "filter": {
    "external_order_id": "order67890"
  }
}
```

---

### 6.12. Поиск билетов по штрихкоду
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/find
```
**Body:**
```json
{
  "filter": {
    "barcode": "872964136579"
  }
}
```

---

### 6.13. Поиск билетов по нескольким критериям
**Запрос:**
```
POST https://qtickets.ru/api/partners/v1/tickets/find
```
**Body:**
```json
{
  "filter": {
    "external_order_id": "6a5cc185-bc59-451f-b7cb-94376476ae01",
    "external_id": ["ticket12345"],
    "barcode": ["872964136579", "879979255977"],
    "id": [134857, 134858]
  }
}
```

---

### 6.14. Получить статус мест (устаревший метод, но может работать)
**Запрос:**
```
GET https://qtickets.ru/api/partners/v1/events/seats/{EVENT_ID}
```
**Примеры:**
- `GET https://qtickets.ru/api/partners/v1/events/seats/12`

---

### 6.15. Получить статус мест для конкретного сеанса
**Запрос:**
```
GET https://qtickets.ru/api/partners/v1/events/seats/{EVENT_ID}/{SHOW_ID}
```
**Примеры:**
- `GET https://qtickets.ru/api/partners/v1/events/seats/12/21`

---

## 7. ДОПОЛНИТЕЛЬНЫЕ ТЕСТОВЫЕ СЦЕНАРИИ

### 7.1. Проверка авторизации (с неверным токеном)
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/events
```
**Заголовки:**
```
Authorization: Bearer INVALID_TOKEN_12345
```
**Ожидаемый ответ:** `WRONG_AUTHORIZATION`

---

### 7.2. Проверка несуществующего заказа
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/orders/999999999
```
**Ожидаемый ответ:** Ошибка 404 или `ORDER_NOT_FOUND`

---

### 7.3. Проверка несуществующего мероприятия
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/events/999999999
```
**Ожидаемый ответ:** `EVENT_NOT_FOUND`

---

### 7.4. Проверка с пустым телом где требуется
**Запрос:**
```
POST https://qtickets.ru/api/rest/v1/clients
```
**Body:** `{}`
**Ожидаемый ответ:** `VALIDATION_ERROR`

---

### 7.5. Проверка с неверными параметрами
**Запрос:**
```
GET https://qtickets.ru/api/rest/v1/orders
```
**Body:**
```json
{
  "where": [
    {
      "column": "invalid_column",
      "value": 1
    }
  ]
}
```
**Ожидаемый ответ:** `VALIDATION_ERROR` или пустой результат

---

## 8. ВАЖНЫЕ ЗАМЕЧАНИЯ

### Формат даты/времени
Все даты должны быть в формате ISO 8601 с часовым поясом:
```
2025-11-07T19:30:00+03:00
```

### Замена переменных
Перед тестированием замените:
- `YOUR_TOKEN` → ваш реальный API токен
- `{EVENT_ID}` → ID вашего мероприятия (например, 12, 33)
- `{SHOW_ID}` → ID сеанса (например, 41, 4076)
- `{ORDER_ID}` → ID заказа (например, 4360)
- `{BASKET_ID}` → ID билета в корзине (например, 63993)
- `{CLIENT_ID}` → ID клиента (например, 235)

### Возможные коды ошибок
- `UNKNOWN_ERROR` — неизвестная ошибка
- `WRONG_AUTHORIZATION` — неверный токен
- `EVENT_NOT_FOUND` — мероприятие не найдено
- `SEAT_NOT_FOUND` — место не найдено
- `SEAT_NOT_AVAILABLE` — место недоступно
- `TICKET_NOT_FOUND` — билет не найден
- `VALIDATION_ERROR` — ошибка валидации

### Примечание по GET-запросам с телом
В документации указано, что некоторые GET-запросы принимают JSON в теле. Если ваш HTTP-клиент не поддерживает это, попробуйте передать параметры через query string.

---

## ГОТОВО! 

Всего составлено **50+ вариантов запросов** для тестирования всех методов API.
