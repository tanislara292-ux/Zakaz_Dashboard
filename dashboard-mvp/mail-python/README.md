# Gmail → ClickHouse Инжестор

Этот компонент извлекает данные о продажах из писем Gmail и загружает их в ClickHouse.

## Установка и настройка

### 1. Установка зависимостей

```bash
cd mail-python
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настройка Gmail API

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите **Gmail API**
4. Создайте **OAuth 2.0 Client ID** (Desktop application)
5. Скачайте `credentials.json` и положите в `secrets/gmail/`

### 3. Настройка окружения

```bash
cp .env.sample .env
```

Отредактируйте `.env`:

```bash
# Gmail search query
GMAIL_QUERY=subject:"Отчет продаж" OR subject:"QTickets" newer_than:30d

# Пути к OAuth-кредам
GMAIL_CREDS_PATH=secrets/gmail/credentials.json
GMAIL_TOKEN_PATH=secrets/gmail/token.json

# ClickHouse настройки
CH_HOST=<your-proxy-domain>
CH_PORT=443
CH_SECURE=true
CH_USERNAME=etl_writer
CH_PASSWORD=<password>
CH_DATABASE=zakaz

# Локаль для чисел с запятыми
DECIMAL_COMMA=true
```

## Использование

### Тестовый запуск (dry-run)

```bash
python gmail_ingest.py --dry-run --limit 5
```

### Полная загрузка

```bash
python gmail_ingest.py
```

## Структура данных

### Сырая таблица `zakaz.stg_mail_sales_raw`

| Поле | Тип | Описание |
|------|-----|----------|
| msg_id | String | ID сообщения |
| msg_received_at | DateTime | Время получения письма |
| source | String | Источник ('gmail') |
| event_date | Date | Дата события |
| event_id | String | ID события |
| event_name | String | Название события |
| city | String | Город |
| tickets_sold | Int32 | Продано билетов |
| revenue | Float64 | Выручка |
| refunds | Float64 | Возвраты |
| currency | String | Валюта |
| row_hash | String | Хэш строки для дедупликации |
| _ingested_at | DateTime | Время загрузки |

### Витрины

- `zakaz.v_sales_latest` - Последние значения по ключу (без дублей)
- `zakaz.v_sales_14d` - Агрегаты за последние 14 дней
- `zakaz.v_sales_combined` - Объединенные данные из почты и QTickets

## Поддерживаемые форматы

- CSV вложения
- HTML таблицы в теле письма
- Различные разделители (`,` и `;`)
- Различные кодировки (UTF-8, CP1251)
- Числа с запятой в качестве десятичного разделителя

## Автоматизация

Для регулярного запуска используйте systemd timer (см. `../infra/systemd/`):

```bash
# Включить таймер
systemctl enable --now gmail-ingest.timer

# Проверить статус
systemctl list-timers | grep gmail-ingest
```

## Диагностика

### Проверка подключения к ClickHouse

```bash
clickhouse-client -q "SELECT count() FROM zakaz.stg_mail_sales_raw"
```

### Проверка последних данных

```bash
clickhouse-client -q "SELECT * FROM zakaz.v_sales_14d ORDER BY d DESC LIMIT 5"
```

### Логирование

Скрипт выводит информацию о:
- Найденных сообщениях
- Извлеченных строках
- Ошибках парсинга
- Загруженных данных