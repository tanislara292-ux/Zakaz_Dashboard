# План до «зелёного» дашборда

Это руководство описывает полный цикл настройки почтового инжестора для автоматической загрузки данных о продажах из Gmail в ClickHouse и визуализации в DataLens.

## Обзор архитектуры

```
Gmail → [gmail_ingest.py] → ClickHouse → DataLens
   ↑                              ↓
systemd timer               Caddy HTTPS прокси
```

## Компоненты

### 1. ClickHouse: таблицы и витрины

DDL-скрипт: [`infra/clickhouse/init_mail.sql`](infra/clickhouse/init_mail.sql)

- `zakaz.stg_mail_sales_raw` - сырые данные из почты
- `zakaz.v_sales_latest` - витрина без дублей
- `zakaz.v_sales_14d` - агрегаты за 14 дней
- `zakaz.v_sales_combined` - объединение с QTickets

### 2. Почтовый инжестор (Gmail → ClickHouse)

Структура: [`mail-python/`](mail-python/)

- `gmail_ingest.py` - основной скрипт инжестора
- `requirements.txt` - зависимости Python
- `.env.sample` - шаблон конфигурации
- `init_clickhouse.sh` - скрипт инициализации БД

### 3. Планировщик (systemd timer)

Файлы: [`infra/systemd/gmail-ingest.service`](infra/systemd/gmail-ingest.service) и [`infra/systemd/gmail-ingest.timer`](infra/systemd/gmail-ingest.timer)

Автоматический запуск каждые 15 минут.

### 4. DataLens: подключение и визуализация

Инструкция: [`docs/DATALENS_MAIL_SETUP.md`](docs/DATALENS_MAIL_SETUP.md)

## Развертывание

### Шаг 1: Подготовка ClickHouse

```bash
# Выполнить DDL
clickhouse-client --multiquery < infra/clickhouse/init_mail.sql

# Проверить создание таблиц
clickhouse-client --query "SHOW TABLES FROM zakaz LIKE '%sales%'"
```

### Шаг 2: Настройка Gmail API

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте проект и включите Gmail API
3. Создайте OAuth 2.0 Client ID (Desktop application)
4. Скачайте `credentials.json` в `mail-python/secrets/gmail/`

### Шаг 3: Настройка инжестора

```bash
cd mail-python

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Настроить конфигурацию
cp .env.sample .env
# Отредактировать .env с вашими параметрами

# Тестовый запуск
python gmail_ingest.py --dry-run --limit 3
```

### Шаг 4: Автоматизация

```bash
# Скопировать systemd файлы
sudo cp infra/systemd/gmail-ingest.* /etc/systemd/system/

# Включить таймер
sudo systemctl daemon-reload
sudo systemctl enable --now gmail-ingest.timer

# Проверить статус
sudo systemctl list-timers | grep gmail-ingest
```

### Шаг 5: Настройка DataLens

Следуйте инструкции в [`docs/DATALENS_MAIL_SETUP.md`](docs/DATALENS_MAIL_SETUP.md)

## Проверка работоспособности

### 1. Проверка загрузки данных

```bash
# Количество строк в сырой таблице
clickhouse-client -q "SELECT count() FROM zakaz.stg_mail_sales_raw"

# Последние данные
clickhouse-client -q "SELECT * FROM zakaz.v_sales_14d ORDER BY d DESC LIMIT 5"
```

### 2. Проверка автоматизации

```bash
# Логи systemd
journalctl -u gmail-ingest.service -n 50

# Статус таймера
systemctl status gmail-ingest.timer
```

### 3. Проверка DataLens

- Подключитесь к ClickHouse в DataLens
- Выполните тестовый запрос в SQL-консоли
- Создайте датасет и дашборд

## Диагностика проблем

### Нет данных из Gmail

1. Проверьте OAuth-токен:
   ```bash
   ls -la mail-python/secrets/gmail/token.json
   ```

2. Проверьте Gmail query в `.env`:
   ```bash
   grep GMAIL_QUERY mail-python/.env
   ```

3. Запустите вручную с отладкой:
   ```bash
   cd mail-python
   python gmail_ingest.py --dry-run --limit 5
   ```

### Проблемы с ClickHouse

1. Проверьте подключение:
   ```bash
   clickhouse-client --query "SELECT 1"
   ```

2. Проверьте права:
   ```bash
   clickhouse-client --query "SHOW GRANTS FOR etl_writer"
   ```

3. Проверьте таблицы:
   ```bash
   clickhouse-client --query "SHOW TABLES FROM zakaz"
   ```

### Проблемы с DataLens

1. Проверьте права пользователя `datalens_reader`
2. Проверьте HTTPS-прокси (Caddy)
3. Проверьте сеть между DataLens и ClickHouse

## Мониторинг

### Метрики качества данных

```sql
-- Свежесть данных
SELECT 
  max(_ingested_at) as last_update,
  dateDiff('minute', max(_ingested_at), now()) as minutes_ago
FROM zakaz.stg_mail_sales_raw;

-- Объем данных за сегодня
SELECT 
  count() as rows_today,
  sum(tickets_sold) as tickets_today,
  sum(revenue) as revenue_today
FROM zakaz.v_sales_latest
WHERE event_date = today();
```

### Алерты

Настройте алерты в DataLens или внешней системе мониторинга:

- Нет данных более 1 часа
- Резкое падение объема данных
- Ошибки в логах systemd

## Дальнейшее развитие

1. **Расширение источников**: добавить другие почтовые ящики
2. **Улучшение парсинга**: поддержка更多 форматов
3. **Валидация данных**: проверки качества на лету
4. **Алертинг**: уведомления о проблемах
5. **Оптимизация**: кэширование, индексы

## Поддержка

При возникновении проблем:

1. Проверьте логи: `journalctl -u gmail-ingest.service -f`
2. Проверьте документацию: [`mail-python/README.md`](mail-python/README.md)
3. Проверьте диагностику: [`docs/DATALENS_MAIL_SETUP.md`](docs/DATALENS_MAIL_SETUP.md)