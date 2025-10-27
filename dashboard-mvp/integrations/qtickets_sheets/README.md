# QTickets Google Sheets Integration

Интеграция для загрузки данных QTickets из Google Sheets в ClickHouse.

## Обзор

Модуль `qtickets_sheets` предназначен для замены нестабильного QTickets API на надежный источник данных из Google Sheets. Интеграция обеспечивает:

- Чтение данных из Google Sheets (Events, Inventory, Sales)
- Нормализацию и валидацию данных
- Идемпотентную загрузку с дедупликацией
- Автоматическое выполнение каждые 15 минут

## Структура модуля

```
integrations/qtickets_sheets/
├── __init__.py          # Инициализация модуля
├── loader.py            # Точка входа (CLI)
├── gsheets_client.py    # Клиент для работы с Google Sheets API
├── transform.py         # Трансформация и нормализация данных
├── upsert.py           # Upsert операции в ClickHouse
└── README.md            # Документация
```

## Требования

### Зависимости

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Переменные окружения

Создайте файл `secrets/.env.qtickets_sheets`:

```env
# Google Sheets API
GSERVICE_JSON=secrets/google/sa.json

# Идентификаторы таблиц (spreadsheetId из URL)
SHEET_ID_SALES=1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
SHEET_ID_EVENTS=1bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
SHEET_ID_INVENTORY=1ccccccccccccccccccccccccccccccccccc

# Названия листов внутри таблиц
TAB_SALES=Sales
TAB_EVENTS=Events
TAB_INVENTORY=Inventory

# Поля-ключи для дедупликации
KEY_SALES=date|event_id|city
KEY_EVENTS=event_id|event_date|city
KEY_INVENTORY=event_id|city

# Таймзона и локаль
TZ=Europe/Moscow
LOCALE=ru_RU
```

### Настройка доступа к Google Sheets

1. Создайте сервисный аккаунт в Google Cloud Console
2. Скачайте JSON-файл с ключами сервисного аккаунта
3. Разместите файл в `secrets/google/sa.json`
4. Расшарьте Google Sheets на email сервисного аккаунта с правами Viewer

## Схемы данных

### Events

Обязательные поля:
- `event_id` - ID мероприятия
- `event_name` - Название мероприятия
- `event_date` - Дата мероприятия (YYYY-MM-DD)
- `city` - Город

Опциональные поля:
- `tickets_total` - Общее количество билетов
- `tickets_left` - Доступно билетов

### Inventory

Обязательные поля:
- `event_id` - ID мероприятия
- `city` - Город

Опциональные поля:
- `tickets_total` - Общее количество билетов
- `tickets_left` - Доступно билетов

### Sales

Обязательные поля:
- `date` - Дата продажи (YYYY-MM-DD)
- `event_id` - ID мероприятия
- `city` - Город
- `tickets_sold` - Количество проданных билетов
- `revenue` - Выручка

Опциональные поля:
- `event_name` - Название мероприятия
- `refunds` - Сумма возвратов
- `currency` - Валюта (по умолчанию RUB)

## Использование

### Ручной запуск

```bash
# Загрузка за последние 30 дней
python -m integrations.qtickets_sheets.loader --envfile secrets/.env.qtickets_sheets --ch-env secrets/.env.ch

# Загрузка за указанный период
python -m integrations.qtickets_sheets.loader --envfile secrets/.env.qtickets_sheets --ch-env secrets/.env.ch --since 2023-10-01 --to 2023-10-31

# Тестовый режим (без записи в ClickHouse)
python -m integrations.qtickets_sheets.loader --envfile secrets/.env.qtickets_sheets --ch-env secrets/.env.ch --dry-run --verbose
```

### Автоматизация через systemd

```bash
# Включение таймера
sudo ./ops/systemd/manage_timers.sh enable qtickets_sheets

# Проверка статуса
./ops/systemd/manage_timers.sh status qtickets_sheets

# Просмотр логов
./ops/systemd/manage_timers.sh logs qtickets_sheets
```

## Таблицы ClickHouse

### Стейджинг таблицы

- `zakaz.stg_qtickets_sheets_raw` - Сырые данные из Google Sheets
- `zakaz.stg_qtickets_sheets_events` - Трансформированные мероприятия
- `zakaz.stg_qtickets_sheets_inventory` - Трансформированный инвентарь
- `zakaz.stg_qtickets_sheets_sales` - Трансформированные продажи

### Факт таблицы

- `zakaz.dim_events` - Мероприятия (справочник)
- `zakaz.fact_qtickets_inventory` - Инвентарь
- `zakaz.fact_qtickets_sales` - Продажи

### Метаданные

- `zakaz.meta_job_runs` - Информация о запусках задач

## Мониторинг

### Healthcheck эндпоинты

- `GET /healthz/qtickets_sheets` - Состояние интеграции
- `GET /healthz/detailed` - Детальная проверка
- `GET /healthz/freshness` - Свежесть данных

### Smoke-проверки

```sql
-- Проверка наличия данных
SELECT count() FROM zakaz.fact_qtickets_sales WHERE date >= today() - 3;

-- Проверка уникальности мероприятий
SELECT uniqExact(event_id) FROM zakaz.dim_events;

-- Проверка свежести данных
SELECT max(_ver) FROM zakaz.stg_qtickets_sheets_raw WHERE _ingest_ts >= now() - INTERVAL 1 HOUR;
```

## Трассировка ошибок

### Логи

```bash
# Просмотр логов systemd
journalctl -u qtickets_sheets.service -n 100

# Просмотр логов с фильтрацией
journalctl -u qtickets_sheets.service --since "2023-10-01" --until "2023-10-02"
```

### Метаданные запусков

```sql
-- Последние запуски
SELECT * FROM zakaz.meta_job_runs 
WHERE job = 'qtickets_sheets' 
ORDER BY started_at DESC 
LIMIT 10;

-- Статистика за последние 7 дней
SELECT 
    status,
    count() as runs,
    avg(rows_processed) as avg_rows
FROM zakaz.meta_job_runs
WHERE job = 'qtickets_sheets' 
  AND started_at >= today() - 7
GROUP BY status;
```

## Восстановление после сбоев

### Проблемы с доступом к Google Sheets

1. Проверьте права доступа к таблицам
2. Убедитесь, что сервисный аккаунт расшарен на таблицы
3. Проверьте корректность JSON файла с ключами

```bash
# Проверка доступа
python -c "
from integrations.qtickets_sheets.gsheets_client import GoogleSheetsClient
client = GoogleSheetsClient()
info = client.get_sheet_info(os.getenv('SHEET_ID_SALES'))
print(info)
"
```

### Проблемы с данными

1. Проверьте наличие обязательных полей
2. Убедитесь в корректности формата дат
3. Проверьте числовые поля на наличие нечисловых значений

```bash
# Тестовая трансформация
python -m integrations.qtickets_sheets.loader --dry-run --verbose
```

### Проблемы с ClickHouse

1. Проверьте доступность ClickHouse
2. Убедитесь в наличии необходимых таблиц
3. Проверьте права пользователя

```bash
# Проверка подключения
python -c "
from integrations.common import get_client
client = get_client('secrets/.env.ch')
result = client.execute('SELECT version()')
print(result.first_row[0])
"
```

## Обслуживание

### Очистка стейджинг таблиц

```sql
-- Ручная очистка старых данных
ALTER TABLE zakaz.stg_qtickets_sheets_raw 
DELETE WHERE _ingest_ts < now() - INTERVAL 30 DAY;
```

### Обновление конфигурации

```bash
# Обновление переменных окружения
nano secrets/.env.qtickets_sheets

# Перезапуск таймера
sudo ./ops/systemd/manage_timers.sh restart qtickets_sheets
```

## Разработка

### Тестирование

```bash
# Запуск тестов
python -m pytest tests/test_qtickets_sheets.py -v

# Тестирование с покрытием
python -m pytest tests/test_qtickets_sheets.py --cov=integrations/qtickets_sheets
```

### Добавление новых полей

1. Обновите схемы в `transform.py`
2. Добавьте поля в DDL ClickHouse
3. Обновите обязательные заголовки в `loader.py`
4. Протестируйте с `--dry-run`

## Версионирование

- v1.0.0 - Базовая функциональность
- v1.1.0 - Добавлена поддержка инвентаря
- v1.2.0 - Улучшена обработка ошибок

## Контакты

- Поддержка: ads-irsshow@yandex.ru
- Документация: `docs/`
- Исходный код: `integrations/qtickets_sheets/`