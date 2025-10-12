# RUNBOOK: ETL Оркестрация и мониторинг

## Обзор

Этот документ описывает систему оркестрации ETL-процессов проекта Zakaz, включая systemd таймеры, мониторинг выполнения, алерты и backfill-сценарии.

## Компоненты системы

### 1. Метаданные и мониторинг в ClickHouse

#### Таблицы метаданных

- `meta.etl_runs` - реестр прогонов ETL
- `meta.etl_alerts` - реестр алертов
- `meta.v_quality_last_day` - представление для контроля качества данных за последний день

#### Структура таблицы `meta.etl_runs`

```sql
CREATE TABLE meta.etl_runs
(
    job            LowCardinality(String),  -- Название job'а
    run_id         UUID,                    -- Уникальный ID прогона
    started_at     DateTime,                -- Время начала
    finished_at    DateTime,                -- Время окончания
    status         LowCardinality(String),  -- 'ok' | 'error'
    rows_written   UInt64,                  -- Количество записанных строк
    rows_read      UInt64,                  -- Количество прочитанных строк
    err_msg        String,                  -- Сообщение об ошибке
    from_date      Date,                    -- Начальная дата обработки
    to_date        Date,                    -- Конечная дата обработки
    host           String,                  -- Хост выполнения
    version_tag    String                   -- Версия кода (git commit)
)
ENGINE = MergeTree
ORDER BY (started_at, job)
PARTITION BY toYYYYMM(started_at);
```

### 2. Единые точки входа

#### `ops/run_job.sh`

Основной скрипт для запуска всех ETL job'ов с логированием и записью в `meta.etl_runs`.

Поддерживаемые job'ы:
- `vk_fetch` - сбор сырых данных из VK Ads
- `build_dm_vk` - построение витрины VK Ads
- `build_dm_sales` - построение витрины продаж
- `backfill_all` - полный backfill за период

Использование:
```bash
bash ops/run_job.sh <job_name> [--additional_args]
```

#### `ops/alert_notify.py`

Скрипт для отправки уведомлений в Telegram.

Использование:
```bash
python ops/alert_notify.py "Сообщение для отправки"
```

Требуемые переменные окружения:
- `TG_BOT_TOKEN` - токен Telegram бота
- `TG_CHAT_ID` - ID чата для отправки

#### `ops/healthcheck.py`

Скрипт для проверки качества данных за последний день.

Использование:
```bash
python ops/healthcheck.py
```

Проверки:
- Наличие данных в витринах продаж и VK Ads за вчера
- Отсутствие отрицательных значений

#### `ops/backfill.py`

Скрипт для полного backfill'а за указанный период.

Использование:
```bash
python ops/backfill.py --from 2025-10-01 --to 2025-10-10
```

### 3. Оркестрация на сервере (systemd)

#### Шаблоны сервисов

- `infra/systemd/etl@.service` - шаблон сервиса для любого job'а
- `infra/systemd/etl@.timer` - шаблон таймера

#### Установка и настройка

1. Копирование файлов systemd:
```bash
sudo cp infra/systemd/etl@.service /etc/systemd/system/
sudo cp infra/systemd/etl@.timer   /etc/systemd/system/
sudo systemctl daemon-reload
```

2. Включение таймеров для конкретных job'ов:
```bash
sudo systemctl enable --now etl@vk_fetch.timer
sudo systemctl enable --now etl@build_dm_vk.timer
sudo systemctl enable --now etl@build_dm_sales.timer
```

3. Проверка статуса:
```bash
systemctl list-timers | grep etl@
journalctl -u etl@vk_fetch.service -n 100 --no-pager
```

#### Расписание по умолчанию

- `vk_fetch` - 05:35 MSK
- `build_dm_vk` - 05:50 MSK
- `build_dm_sales` - 06:05 MSK

Для изменения расписания создайте override-файл:
```bash
sudo systemctl edit etl@vk_fetch.timer
```

И добавьте:
```ini
[Timer]
OnCalendar=*-*-* 06:00:00 Europe/Moscow
```

### 4. GitHub Actions

#### `etl_dispatch.yml`

Workflow для ручных запусков и резервного выполнения.

Возможности:
- Ручной запуск через `workflow_dispatch`
- Поддержка всех job'ов
- Backfill за указанный период
- Автоматические алерты при ошибках

Использование:
1. Перейдите в раздел Actions в GitHub
2. Выберите workflow "ETL Dispatch"
3. Нажмите "Run workflow"
4. Выберите job и при необходимости укажите даты для backfill

### 5. Алерты и мониторинг

#### Типы алертов

- `RUN_FAILED` - неудачное выполнение job'а
- `ZERO_ROWS` - отсутствие данных в витрине
- `ANOMALY` - аномальные значения (отрицательные суммы и т.д.)

#### Настройка алертов

1. Создайте Telegram бота и получите токен
2. Получите ID чата для отправки сообщений
3. Добавьте переменные в `.env`:
```
TG_BOT_TOKEN=your_bot_token
TG_CHAT_ID=your_chat_id
```

4. Для GitHub Actions добавьте секреты:
```
TG_BOT_TOKEN
TG_CHAT_ID
```

#### Мониторинг в DataLens

Создайте датасет на основе таблицы `meta.etl_runs` для мониторинга:
- Статусы выполнений
- Длительность выполнения
- Количество обработанных строк
- Частота ошибок

## Процедуры

### Запуск job'а вручную

Через systemd:
```bash
sudo systemctl start etl@vk_fetch.service
```

Через скрипт:
```bash
bash ops/run_job.sh vk_fetch
```

### Backfill за период

```bash
python ops/backfill.py --from 2025-10-01 --to 2025-10-10
```

### Проверка качества данных

```bash
python ops/healthcheck.py
```

### Просмотр логов

```bash
journalctl -u etl@vk_fetch.service -f
```

### Просмотр истории выполнений

```sql
SELECT 
    job,
    started_at,
    finished_at,
    status,
    rows_written,
    err_msg
FROM meta.etl_runs
ORDER BY started_at DESC
LIMIT 20;
```

## Поиск и устранение проблем

### Job не запускается

1. Проверьте статус сервиса:
```bash
systemctl status etl@vk_fetch.service
```

2. Проверьте логи:
```bash
journalctl -u etl@vk_fetch.service -n 50
```

3. Проверьте наличие `.env` файла с правильными правами доступа

### Ошибки подключения к ClickHouse

1. Проверьте доступность ClickHouse:
```bash
curl "http://localhost:8123/?query=SELECT%201"
```

2. Проверьте учетные данные в `.env`

3. Проверьте права пользователя `etl_writer`

### Отсутствие данных в витринах

1. Запустите healthcheck:
```bash
python ops/healthcheck.py
```

2. Проверьте наличие данных в стейджинг-таблицах:
```sql
SELECT count() FROM zakaz.stg_qtickets_sales WHERE event_date = today() - 1;
SELECT count() FROM zakaz.stg_vk_ads_daily WHERE stat_date = today() - 1;
```

3. Проверьте логи выполнения job'ов

### Алерты не приходят

1. Проверьте токен бота и ID чата:
```bash
python ops/alert_notify.py "Test message"
```

2. Проверьте переменные окружения

3. Убедитесь, что бот имеет доступ к чату

## Обслуживание

### Обновление скриптов

1. Замените файлы в `ops/`
2. Перезапустите активные сервисы:
```bash
sudo systemctl restart etl@vk_fetch.service
```

### Изменение расписания

1. Создайте override-файл:
```bash
sudo systemctl edit etl@vk_fetch.timer
```

2. Добавьте новые настройки
3. Перезагрузите systemd:
```bash
sudo systemctl daemon-reload
```

### Очистка старых логов

```bash
sudo journalctl --vacuum-time=30d
```

## Откат изменений

### Отключение таймеров

```bash
sudo systemctl disable --now etl@vk_fetch.timer
sudo systemctl disable --now etl@build_dm_vk.timer
sudo systemctl disable --now etl@build_dm_sales.timer
```

### Удаление сервисов

```bash
sudo rm /etc/systemd/system/etl@.service
sudo rm /etc/systemd/system/etl@.timer
sudo systemctl daemon-reload
```

### Удаление таблиц метаданных

```sql
DROP TABLE meta.etl_runs;
DROP TABLE meta.etl_alerts;
DROP VIEW meta.v_quality_last_day;
DROP DATABASE meta;