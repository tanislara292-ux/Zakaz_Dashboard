# План E2E тестирования реальных источников данных

## Обзор

Документ содержит детальный план для проведения end-to-end тестирования реальных источников данных (QTickets API, Google Sheets) с точным определением проблем и путей их решения.

## Цель тестирования

- Проверить работоспособность загрузчиков реальных данных
- Определить точные причины неработоспособности
- Предоставить конкретные решения для каждой проблемы
- Исключить мок/тестовые данные из финальной системы

## Предоставленные данные

### QTickets API
- **Токен**: `4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ`
- **URL**: `https://api.qtickets.ru/v1`
- **Формат**: CSV/Excel
- **Пример UTM**: `utm_source=yandex&utm_medium=rsya&utm_campaign=703488888&utm_content=17305414105&utm_term=`

### Google Sheets
- **URL**: `https://docs.google.com/spreadsheets/d/1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc`
- **Email**: `chufarovk@gmail.com` (Editor)
- **Лист**: `Лист1`
- **Диапазон**: `A:Z`

## План тестирования

### Шаг 1: Проверка доступности API

#### QTickets API
```bash
# Проверка доступности API с токеном
curl -H "Authorization: Bearer 4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     https://api.qtickets.ru/v1/events

# Проверка списка мероприятий
curl -H "Authorization: Bearer 4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ" \
     https://api.qtickets.ru/v1/events?limit=5

# Проверка данных о продажах
curl -H "Authorization: Bearer 4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ" \
     "https://api.qtickets.ru/v1/sales?date_from=2025-10-13&date_to=2025-10-20"
```

**Возможные проблемы и решения:**
- **Проблема**: `401 Unauthorized`
  - **Причина**: Токен недействителен или неверный
  - **Решение**: Получить новый токен у заказчика

- **Проблема**: `403 Forbidden`
  - **Причина**: Недостаточно прав у токена
  - **Решение**: Запросить токен с правами чтения данных

- **Проблема**: `404 Not Found`
  - **Причина**: URL API неверный или эндпоинт не существует
  - **Решение**: Проверить документацию API и скорректировать URL

- **Проблема**: Таймаут запроса
  - **Причина**: API недоступен или медленный
  - **Решение**: Проверить доступность API, увеличить таймаут

#### Google Sheets API
```bash
# Проверка доступности таблицы
curl "https://docs.google.com/spreadsheets/d/1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc/export?format=csv"

# Проверка конкретного листа
curl "https://docs.google.com/spreadsheets/d/1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc/export?format=csv&gid=0"
```

**Возможные проблемы и решения:**
- **Проблема**: `403 Forbidden`
  - **Причина**: Таблица не доступна публично
  - **Решение**: Настроить доступ "Anyone with link can view" или использовать сервисный аккаунт

- **Проблема**: `400 Bad Request`
  - **Причина**: Неверный ID таблицы или листа
  - **Решение**: Проверить ID таблицы и gid листа

### Шаг 2: Тестирование загрузчиков

#### QTickets загрузчик
```bash
# Запуск с отладкой
cd dashboard-mvp
python3 integrations/qtickets/loader.py \
    --env secrets/.env.qtickets \
    --days 7 \
    --verbose

# Проверка логов
tail -f logs/qtickets.log
```

**Возможные проблемы и решения:**
- **Проблема**: `ModuleNotFoundError: No module named 'clickhouse_connect'`
  - **Причина**: Не установлены зависимости Python
  - **Решение**: `pip install clickhouse-connect`

- **Проблема**: `Connection refused`
  - **Причина**: ClickHouse недоступен
  - **Решение**: Проверить статус контейнера `docker ps | grep ch-zakaz`

- **Проблема**: `Authentication failed`
  - **Причина**: Неверные учетные данные ClickHouse
  - **Решение**: Проверить пароль пользователя в файле .env

- **Проблема**: `Table doesn't exist`
  - **Причина**: Таблица не создана
  - **Решение**: Создать таблицу через DDL скрипт

#### Google Sheets загрузчик
```bash
# Запуск с отладкой
cd dashboard-mvp
python3 archive/sheets/init.py --verbose

# Проверка логов
tail -f logs/sheets.log
```

**Возможные проблемы и решения:**
- **Проблема**: `ModuleNotFoundError: No module named 'google'`
  - **Причина**: Не установлены Google API библиотеки
  - **Решение**: `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`

- **Проблема**: `RetAuthenticationError`
  - **Причина**: Проблемы с аутентификацией Google
  - **Решение**: Настроить сервисный аккаунт и файл credentials.json

- **Проблема**: `HttpError 403`
  - **Причина**: Недостаточно прав доступа к таблице
  - **Решение**: Предоставить доступ "Editor" для сервисного аккаунта

### Шаг 3: Проверка загруженных данных

#### QTickets данные
```sql
-- Проверка загруженных данных
SELECT 
    count() as total_records,
    min(event_date) as earliest_date,
    max(event_date) as latest_date,
    countDistinct(city) as unique_cities,
    countDistinct(event_name) as unique_events
FROM zakaz.stg_qtickets_sales_raw;

-- Проверка структуры данных
DESCRIBE zakaz.stg_qtickets_sales_raw;

-- Проверка примеров данных
SELECT * FROM zakaz.stg_qtickets_sales_raw LIMIT 10;
```

#### Google Sheets данные
```sql
-- Проверка загруженных данных
SELECT 
    count() as total_records,
    min(event_date) as earliest_date,
    max(event_date) as latest_date,
    countDistinct(city) as unique_cities,
    countDistinct(event_name) as unique_events
FROM zakaz.stg_google_sheets_raw;

-- Проверка структуры данных
DESCRIBE zakaz.stg_google_sheets_raw;

-- Проверка примеров данных
SELECT * FROM zakaz.stg_google_sheets_raw LIMIT 10;
```

### Шаг 4: Тестирование агрегации

```sql
-- Проверка обновления представлений
SELECT 
    count() as total_records,
    min(event_date) as earliest_date,
    max(event_date) as latest_date,
    sum(tickets_sold) as total_tickets,
    sum(revenue) as total_revenue
FROM zakaz.v_sales_latest;

-- Проверка корректности агрегации
SELECT 
    event_date,
    city,
    sum(tickets_sold) as tickets,
    sum(revenue) as revenue
FROM zakaz.stg_qtickets_sales_raw
WHERE event_date >= today() - 7
GROUP BY event_date, city
ORDER BY event_date, city;
```

## Скрипты для тестирования

### 1. API доступность
```bash
#!/bin/bash
# api_access_test.sh

echo "=== Проверка доступности API ==="

# QTickets API
echo "1. Проверка QTickets API..."
response=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer 4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ" \
    https://api.qtickets.ru/v1/events)

if [ "$response" = "200" ]; then
    echo "✅ QTickets API доступен"
else
    echo "❌ QTickets API недоступен (HTTP $response)"
    echo "   Возможные причины:"
    echo "   - Токен неверный или недействителен"
    echo "   - API URL неверный"
    echo "   - Сетевые проблемы"
fi

# Google Sheets API
echo "2. Проверка Google Sheets API..."
response=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://docs.google.com/spreadsheets/d/1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc/export?format=csv")

if [ "$response" = "200" ]; then
    echo "✅ Google Sheets API доступен"
else
    echo "❌ Google Sheets API недоступен (HTTP $response)"
    echo "   Возможные причины:"
    echo "   - Таблица не доступна публично"
    echo "   - ID таблицы неверный"
    echo "   - Сетевые проблемы"
fi
```

### 2. Загрузчики данных
```bash
#!/bin/bash
# data_loaders_test.sh

echo "=== Тестирование загрузчиков данных ==="

# QTickets загрузчик
echo "1. Тестирование QTickets загрузчика..."
cd dashboard-mvp

# Создание директории логов
mkdir -p logs/real_data_test

# Запуск с отладкой
if python3 integrations/qtickets/loader.py \
    --env secrets/.env.qtickets \
    --days 3 \
    > logs/real_data_test/qtickets_debug.log 2>&1; then
    echo "✅ QTickets загрузчик выполнен успешно"
    
    # Проверка загруженных данных
    count=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_qtickets_sales_raw" --format=TabSeparated 2>/dev/null || echo "0")
    if [ "$count" -gt 0 ]; then
        echo "✅ Данные QTickets загружены: $count записей"
    else
        echo "❌ Данные QTickets не загружены"
    fi
else
    echo "❌ QTickets загрузчик завершился с ошибкой"
    echo "   Логи: logs/real_data_test/qtickets_debug.log"
    tail -20 logs/real_data_test/qtickets_debug.log
fi

# Google Sheets загрузчик
echo "2. Тестирование Google Sheets загрузчика..."
if python3 archive/sheets/init.py > logs/real_data_test/sheets_debug.log 2>&1; then
    echo "✅ Google Sheets загрузчик выполнен успешно"
    
    # Проверка загруженных данных
    count=$(docker exec ch-zakaz clickhouse-client --database=zakaz --query="SELECT count() FROM stg_google_sheets_raw" --format=TabSeparated 2>/dev/null || echo "0")
    if [ "$count" -gt 0 ]; then
        echo "✅ Данные Google Sheets загружены: $count записей"
    else
        echo "❌ Данные Google Sheets не загружены"
    fi
else
    echo "❌ Google Sheets загрузчик завершился с ошибкой"
    echo "   Логи: logs/real_data_test/sheets_debug.log"
    tail -20 logs/real_data_test/sheets_debug.log
fi
```

## Ожидаемые результаты

### Успешное тестирование
- ✅ API доступны и возвращают данные
- ✅ Загрузчики выполняются без ошибок
- ✅ Данные загружаются в ClickHouse
- ✅ Агрегация работает корректно

### Проблемы и решения

### QTickets API
- **Токен неверный**: Получить новый токен у заказчика
- **API недоступен**: Проверить URL и доступность
- **Права недостаточны**: Запросить токен с нужными правами

### Google Sheets
- **Таблица не доступна**: Настроить публичный доступ или сервисный аккаунт
- **ID неверный**: Проверить ID таблицы в URL
- **Права недостаточны**: Предоставить доступ "Editor"

### Загрузчики
- **Модули отсутствуют**: Установить зависимости Python
- **ClickHouse недоступен**: Проверить статус контейнера
- **Таблицы отсутствуют**: Создать таблицы через DDL

## Заключение

Тестирование реальных источников данных позволит точно определить проблемы и предоставить конкретные решения для их устранения. После успешного тестирования система будет готова к работе с реальными данными в DataLens.

---

**Статус плана**: 📋 План готов к выполнению
**Дата создания**: 20.10.2025
**Исполнитель**: Архитектурный режим
**Версия**: 1.0.0