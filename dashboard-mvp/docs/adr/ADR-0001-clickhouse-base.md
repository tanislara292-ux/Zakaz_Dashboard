# ADR-0001: Развертывание ClickHouse (single-node) с базовыми схемами stg/core

Дата: 2025-10-11
Контекст: MVP сейчас работает на Google Sheets (QTickets + VK Ads) и DataLens. Для устранения "стыков" и получения управляемого контура данных начинаем миграцию в нормальную БД. Первый шаг - поднять свой ClickHouse на удаленном сервере, зафиксировать схемы, завести роли/пользователей и прогнать первичную загрузку из существующих листов для проверок.

Решение:
1. Развернуть ClickHouse в Docker Compose на удаленном сервере
2. Создать БД `zakaz` и таблицы `stg_*` (стейджинг) и `core_*` (ядро) с детерминированными ключами и стратегией дедупликации
3. Создать пользователей `etl_writer` (INSERT) и `datalens_reader` (READ)
4. Реализовать простую утилиту загрузки из Google Sheets → `stg_qtickets_sales` (первые 1-7 дней данных для smoke-теста)
5. Подготовить документацию и инструкции по развертыванию

Контракты данных:

### 1) Стейджинг — заказы QTickets

`stg_qtickets_sales` — ReplacingMergeTree по "логическому" PK

```sql
CREATE TABLE IF NOT EXISTS zakaz.stg_qtickets_sales
(
    report_date      Date,              -- дата формирования/получения отчёта (из письма/выгрузки)
    event_date       Date,              -- дата мероприятия
    event_name       String,            -- нормализованное имя мероприятия
    city             String,            -- город (нормализованный)
    tickets_sold     UInt32,
    revenue          Decimal(12,2),
    refunds_amount   Decimal(12,2) DEFAULT 0,
    currency         FixedString(3),

    src_message_id   String,            -- идентификатор исходного сообщения/пакета
    src_message_ts   DateTime,          -- время исходного сообщения/выгрузки
    dedup_key        String,            -- "<report_date>|<event_date>|<event_name>|<city>" в lower-case
    ingested_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (report_date, event_date, city, event_name);
```

### 2) Стейджинг — VK Ads (суточная статистика)

```sql
CREATE TABLE IF NOT EXISTS zakaz.stg_vk_ads_daily
(
    stat_date   Date,
    campaign_id UInt64,
    ad_id       UInt64,
    impressions UInt64,
    clicks      UInt64,
    spent       Decimal(12,2),

    utm_source  String,
    utm_medium  String,
    utm_campaign String,
    utm_content String,
    utm_term    String,

    dedup_key   String,               -- "<stat_date>|<campaign_id>|<ad_id>"
    ingested_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (stat_date, campaign_id, ad_id);
```

### 3) Каркас ядра — фактовая таблица продаж (пока пустая логика, только DDL)

```sql
CREATE TABLE IF NOT EXISTS zakaz.core_sales_fct
(
    sale_date     Date,
    event_date    Date,
    event_name    String,
    city          String,
    tickets_sold  UInt32,
    revenue       Decimal(12,2),
    refunds_amount Decimal(12,2),
    currency      FixedString(3),
    load_ts       DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (sale_date, event_date, city, event_name);
```

Стратегия дедупликации:
- В стейджинге используем ReplacingMergeTree с одинаковым PK + ingested_at для дедупликации
- Для консистентных выборок используем FINAL в запросах
- dedup_key формируется как композиция ключевых полей для быстрой проверки дубликатов

Пользователи и роли:
- admin: полные права на БД
- etl_writer: INSERT, SELECT на все таблицы zakaz.*
- datalens_reader: SELECT на все таблицы zakaz.*

Риски:
1. Неверная типизация денег → используем Decimal(12,2), проверяем суммарные ревенью vs исходные
2. Сырые дубликаты → сравниваем count() и countDistinct(dedup_key)
3. Доступы Google → убедиться, что сервис-аккаунт расшарен на нужный Spreadsheet
4. Открытые порты → временно доступ только по нашему офисному/серверному IP (или SSH-туннель); TLS — в следующей задаче

Тест-план:
1. Infra: контейнер поднялся, SELECT version() отвечает
2. DDL: все таблицы созданы, права выданы, пользователи действуют
3. Loader: локально выполняется cli.py с --days 7, вставляет ≥ N строк (N>0)
4. SQL smoke: запросы проверяют дедупликацию и корректность данных

Критерии приёмки (DoD):
- [ ] Docker Compose инициализирует ClickHouse на удалённом сервере, порты доступны
- [ ] Созданы zakaz.stg_qtickets_sales, zakaz.stg_vk_ads_daily, zakaz.core_sales_fct
- [ ] etl_writer имеет INSERT/SELECT, datalens_reader — SELECT
- [ ] Утилита загрузки из Sheets заливает свежие 7 дней в stg_qtickets_sales
- [ ] Дедуп-ключ заполняется, ReplacingMergeTree работает (проверка через FINAL)
- [ ] ADR, ARCHITECTURE, OVERVIEW и CHANGELOG обновлены
- [ ] PR со скринами SQL-проверок и логов загрузки, pre-commit зелёный