# Changelog QTickets Google Sheets Integration

## [1.0.0] - 2025-10-24

### Добавлено
- Новая интеграция `qtickets_sheets` для загрузки данных из Google Sheets
- Полная замена нестабильного QTickets API на надежный источник данных
- Поддержка трех типов данных: Events, Inventory, Sales
- Идемпотентная загрузка с дедупликацией на основе хэшей
- Автоматическое выполнение каждые 15 минут через systemd таймер

### Технические изменения
- **Новые модули**:
  - `integrations/qtickets_sheets/gsheets_client.py` - клиент Google Sheets API
  - `integrations/qtickets_sheets/transform.py` - трансформация и нормализация данных
  - `integrations/qtickets_sheets/upsert.py` - upsert операции в ClickHouse
  - `integrations/qtickets_sheets/loader.py` - точка входа (CLI)

- **Новые таблицы ClickHouse**:
  - `zakaz.stg_qtickets_sheets_raw` - сырые данные из Google Sheets
  - `zakaz.stg_qtickets_sheets_events` - стейджинг мероприятий
  - `zakaz.stg_qtickets_sheets_inventory` - стейджинг инвентаря
  - `zakaz.stg_qtickets_sheets_sales` - стейджинг продаж
  - `zakaz.fact_qtickets_inventory` - факт таблица инвентаря
  - `zakaz.fact_qtickets_sales` - факт таблица продаж

- **Новые представления**:
  - `zakaz.v_qtickets_sales_latest` - актуальные продажи без дублей
  - `zakaz.v_qtickets_sales_14d` - продажи за последние 14 дней
  - `zakaz.v_qtickets_inventory` - инвентарь по мероприятиям
  - `zakaz.v_qtickets_freshness` - свежесть данных

- **Новые systemd юниты**:
  - `qtickets_sheets.service` - сервис загрузчика
  - `qtickets_sheets.timer` - таймер запуска каждые 15 минут

- **Обновления**:
  - `manage_timers.sh` - добавлена поддержка qtickets_sheets
  - `healthcheck_integrations.py` - добавлен эндпоинт `/healthz/qtickets_sheets`
  - `ARCHITECTURE.md` - обновлена схема потоков данных
  - `RUNBOOK_INTEGRATIONS.md` - добавлено руководство по qtickets_sheets

### Конфигурация
- Новый файл конфигурации: `secrets/.env.qtickets_sheets`
- Пример конфигурации: `secrets/.env.qtickets_sheets.sample`
- Поддержка сервисного аккаунта Google для доступа к Sheets

### Мониторинг
- Smoke-проверки: `infra/clickhouse/smoke_checks_qtickets_sheets.sql`
- Healthcheck эндпоинт: `GET /healthz/qtickets_sheets`
- Метаданные запусков в `zakaz.meta_job_runs`

### Документация
- `integrations/qtickets_sheets/README.md` - полное руководство по интеграции
- Примеры использования и отладки
- Инструкции по настройке доступа к Google Sheets

### Совместимость
- Требует Python 3.8+
- Зависимости: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`
- Совместимо с существующей архитектурой ClickHouse

### Миграция
- Старый QTickets API остается функциональным для обратной совместимости
- Рекомендуется отключить `qtickets.timer` после полного перехода на Sheets
- Данные из Sheets и API могут сосуществовать в одной БД

### Безопасность
- Использование сервисного аккаунта Google с минимальными правами
- Хранение учетных данных в `secrets/` (в .gitignore)
- Валидация заголовков перед обработкой данных

### Производительность
- Пакетная загрузка данных (по 10K строк)
- TTL для стейджинг таблиц (7-30 дней)
- Оптимизированные индексы для дедупликации

### Известные ограничения
- Требуется ручное расшаривание Google Sheets на сервисный аккаунт
- Ограничения API Google Sheets (100 запросов в секунду)
- Поддерживаются только форматы дат YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY

### Планы на будущее
- [v1.1.0] Добавление инкрементальной загрузки
- [v1.2.0] Поддержка изменения порядка колонок
- [v1.3.0] Автоматическое обнаружение новых листов
- [v2.0.0] Полная замена QTickets API (деактивация)