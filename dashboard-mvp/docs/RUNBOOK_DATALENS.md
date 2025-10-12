# RUNBOOK: DataLens ↔ ClickHouse подключение

## Обзор

Этот документ описывает процесс подключения DataLens к ClickHouse для создания дашбордов продаж проекта Zakaz.

## Предварительные условия

1. ClickHouse запущен и доступен
2. Пользователь `datalens_reader` создан с необходимыми правами
3. Настроен реверс-прокси (рекомендуемый вариант) или открыт порт 8123

## Варианты доступа к ClickHouse

### Вариант A - Прямой HTTP 8123 с firewall-allowlist

1. На внешнем файерволе/SG откройте порт `8123/tcp` только для egress-адресов DataLens
2. Убедитесь, что `users.d/10-users.xml` не ограничивает `datalens_reader` по сетям

### Вариант B - HTTPS через реверс-прокси (рекомендовано)

1. Настройте домен `ch.your-domain` на сервер с ClickHouse
2. Запустите Caddy в качестве реверс-прокси:
   ```bash
   cd infra/clickhouse
   docker-compose up -d
   ```
3. Проверьте доступность:
   ```bash
   curl -I https://ch.your-domain/?query=SELECT%201
   ```

### Вариант C - SSH-туннель/бастион (временный)

1. Поднимите reverse-туннель с сервера CH на публичный бастион:
   ```bash
   autossh -M 0 -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3" \
     -R 8123:localhost:8123 user@bastion-host
   ```

## Настройка DataLens

### Шаг 1. Создание подключения

1. В DataLens перейдите в **Connections → New → ClickHouse**
2. Тип: **External (self-hosted)**
3. Заполните поля:
   - **Host:** `ch.your-domain` (или публичный IP)
   - **Port:** `443` при варианте B (или `8123` при A/C)
   - **Database:** `zakaz`
   - **Username / Password:** `datalens_reader` / `CLICKHOUSE_DATALENS_READER_PASSWORD`
   - **Secure / TLS:** включить, если 443/TLS
4. **Test connection** → **Create**
5. Название подключения: `ch_zakaz_prod`

### Шаг 2. Создание источника данных

**Способ 1 (рекомендуется): источник по SQL**

1. Создать **Data Source → SQL** в подключении `ch_zakaz_prod`
2. SQL-запрос:
   ```sql
   SELECT
     sale_date,
     event_date,
     city,
     event_name,
     tickets_sold,
     revenue,
     refunds_amount,
     (revenue - refunds_amount) AS net_revenue
   FROM zakaz.v_sales_latest
   ```
3. Имя источника: `src_ch_sales_latest`

**Способ 2: источник по таблице/представлению**

1. Выбрать `zakaz.v_sales_latest` из списка объектов

### Шаг 3. Создание датасета

1. На основе `src_ch_sales_latest` создать **Dataset** с именем `ds_sales`
2. Настройте поля:
   - **Dimensions:** 
     - `sale_date` (Date)
     - `event_date` (Date)
     - `city` (String)
     - `event_name` (String)
   - **Measures (SUM):**
     - `tickets_sold`
     - `revenue`
     - `refunds_amount`
     - `net_revenue`
3. Вычисляемые поля (опционально):
   - `Week` = `toWeek(sale_date)`
   - `City_title` = `INITCAP(city)`

### Шаг 4. Создание дашборда

Создать Dashboard `Zakaz — Sales (MVP)` и добавить 3 виджета:

1. **Time Series (Линия):**
   - Measures: `net_revenue` (SUM)
   - Dimension: `event_date`
   - Фильтры: дата за последние 30/60 дней

2. **Top Cities (Бар):**
   - Measures: `revenue` (SUM)
   - Dimension: `city`
   - Сортировка: по `revenue` desc, Limit = 20

3. **KPI-блоки (карточки):**
   - `SUM(net_revenue)` за последние 7 дней
   - `SUM(tickets_sold)` за последние 7 дней
   - `AVG(ticket_price)` = `SUM(revenue)/NULLIF(SUM(tickets_sold),0)`

Сверху добавить фильтры Dashboard: `event_date (range)`, `city (multi-select)`.

## Контроль качества

### Проверка на дубликаты

В ClickHouse выполните:
```sql
-- Проверка кардинальности
SELECT count() total, countDistinct(dedup_key) uniq
FROM zakaz.stg_qtickets_sales;

-- Проверка представлений
SELECT count() FROM zakaz.v_sales_latest;
SELECT count() FROM zakaz.v_sales_14d;
```

### Сверка с исходниками

Выберите 2-3 города и 2-3 даты — суммы `revenue`/`tickets_sold` в DataLens должны совпадать с SQL в ClickHouse.

### Производительность

Графики за 30-60 дней должны отрабатывать <2-3 сек. Если медленно, переключите виджеты на `v_sales_14d`.

## Управление правами

### Текущие права

```sql
-- Полный доступ к схеме zakaz
GRANT SELECT ON zakaz.* TO datalens_reader;

-- Ограниченный доступ (раскомментируйте при необходимости)
-- REVOKE SELECT ON zakaz.* FROM datalens_reader;
-- GRANT SELECT ON zakaz.v_sales_latest TO datalens_reader;
-- GRANT SELECT ON zakaz.v_sales_14d TO datalens_reader;
-- GRANT SELECT ON zakaz.stg_qtickets_sales TO datalens_reader;
```

## Поиск и устранение проблем

### Проблема: Нет подключения к ClickHouse

1. Проверьте доступность домена:
   ```bash
   curl -I https://ch.your-domain/?query=SELECT%201
   ```
2. Проверьте логи Caddy:
   ```bash
   docker logs ch-zakaz-caddy
   ```
3. Проверьте логи ClickHouse:
   ```bash
   docker logs ch-zakaz
   ```

### Проблема: Медленные запросы

1. Проверьте explain plan:
   ```sql
   EXPLAIN PIPELINE SELECT count() FROM zakaz.v_sales_latest WHERE event_date >= today() - 30;
   ```
2. Используйте `v_sales_14d` для быстрых агрегаций
3. Рассмотрите создание материализованных представлений

### Проблема: Некорректные данные

1. Проверьте наличие дублей:
   ```sql
   SELECT dedup_key, count() as cnt
   FROM zakaz.stg_qtickets_sales
   GROUP BY dedup_key
   HAVING cnt > 1
   LIMIT 10;
   ```
2. Проверьте свежесть данных:
   ```sql
   SELECT max(report_date), max(event_date) FROM zakaz.stg_qtickets_sales;
   ```

## Обслуживание

### Обновление представлений

При изменении логики представлений:
```sql
-- Пересоздание представлений
DROP VIEW IF EXISTS zakaz.v_sales_latest;
CREATE OR REPLACE VIEW zakaz.v_sales_latest AS ...;
```

### Мониторинг

Следите за:
- Размером таблиц `stg_qtickets_sales`
- Временем выполнения запросов к `v_sales_latest`
- Свежестью данных (максимальная дата `report_date`)

## Откат изменений

Для отката изменений:
```sql
-- Удаление представлений
DROP VIEW IF EXISTS zakaz.v_sales_latest;
DROP VIEW IF EXISTS zakaz.v_sales_14d;

-- Возврат к исходным правам
REVOKE SELECT ON zakaz.* FROM datalens_reader;
GRANT SELECT ON zakaz.* TO datalens_reader;
```

В DataLens: удалите подключение, источник, датасет, дашборд.

## EPIC-CH-03: Переключение на материализованные витрины

### Обзор

После реализации EPIC-CH-03 доступны материализованные витрины, которые обеспечивают лучшую производительность по сравнению с представлениями с `FINAL`.

### Новые источники данных

#### Источник src_dm_sales_daily

1. Создание источника:
   ```sql
   SELECT
     event_date,
     sale_date,
     city,
     event_name,
     tickets_sold,
     revenue,
     refunds_amount,
     net_revenue
   FROM zakaz.v_dm_sales_daily
   ```

2. Поля:
   - **Dimensions:** `event_date`, `sale_date`, `city`, `event_name`
   - **Measures:** `tickets_sold`, `revenue`, `refunds_amount`, `net_revenue`

#### Источник src_vk_ads_dm

1. Создание источника:
   ```sql
   SELECT
     stat_date,
     city,
     impressions,
     clicks,
     spend
   FROM zakaz.v_vk_ads_daily
   ```

2. Поля:
   - **Dimensions:** `stat_date`, `city`
   - **Measures:** `impressions`, `clicks`, `spend`

#### Источник src_marketing_roi

1. Создание источника:
   ```sql
   SELECT
     d,
     city,
     net_revenue,
     tickets_sold,
     spend,
     clicks,
     impressions,
     roas,
     cpc,
     cpt
   FROM zakaz.v_marketing_roi_daily
   ```

2. Поля:
   - **Dimensions:** `d`, `city`
   - **Measures:** `net_revenue`, `tickets_sold`, `spend`, `clicks`, `impressions`
   - **Calculated:** `roas`, `cpc`, `cpt`

### Создание дашборда "Marketing vs Sales (MVP)"

1. **ROAS по городам (Бар)**:
   - Measure: `roas`
   - Dimension: `city`
   - Фильтр: последние 30/60 дней
   - Сортировка: по `roas` desc

2. **Динамика Spend и Net Revenue (Две линии, две оси)**:
   - X-ось: `d` (дата)
   - Левая ось: `SUM(net_revenue)` (линия)
   - Правая ось: `SUM(spend)` (линия)
   - Фильтр: последние 30/60 дней

3. **KPI-тайлы (за 7/30 дней)**:
   - `SUM(spend)` / 100 (в рублях)
   - `SUM(net_revenue)` / 100 (в рублях)
   - `ROAS = SUM(net_revenue)/SUM(spend)`
   - `CPT = SUM(spend)/SUM(tickets_sold)` / 100 (в рублях)

### Переключение существующих дашбордов

Для переключения существующих дашбордов с `v_sales_latest` на `v_dm_sales_daily`:

1. Откройте источник `src_ch_sales_latest`
2. Замените SQL-запрос на:
   ```sql
   SELECT
     event_date,
     sale_date,
     city,
     event_name,
     tickets_sold,
     revenue,
     refunds_amount,
     net_revenue
   FROM zakaz.v_dm_sales_daily
   ```
3. Сохраните источник и проверьте датасеты
4. Убедитесь, что данные корректны и графики отображаются правильно

### Преимущества материализованных витрин

- **Производительность**: Запросы выполняются быстрее без `FINAL`
- **Стабильность**: Данные не меняются при перезагрузке таблиц
- **Эффективность**: Оптимизированы под конкретные сценарии использования
- **Надежность**: Поддерживают версионность и idempotent загрузку

### Мониторинг производительности

Сравните производительность запросов:

```sql
-- Старый подход (медленнее)
SELECT count() FROM zakaz.v_sales_latest WHERE event_date >= today() - 30;

-- Новый подход (быстрее)
SELECT count() FROM zakaz.v_dm_sales_daily WHERE event_date >= today() - 30;
```

### Возврат на старые представления

При необходимости отката:

1. Измените SQL-запрос источника обратно на:
   ```sql
   SELECT
     sale_date,
     event_date,
     city,
     event_name,
     tickets_sold,
     revenue,
     refunds_amount,
     (revenue - refunds_amount) AS net_revenue
   FROM zakaz.v_sales_latest
   ```
2. Сохраните источник и проверьте датасеты

## EPIC-CH-05: BI-Package для DataLens

### Обзор

После реализации EPIC-CH-05 доступен полноценный BI-пакет на ClickHouse с готовыми датасетами и дашбордами для анализа продаж, маркетинговых показателей и операционной эффективности.

### Новые источники данных (BI-слой)

#### Источник ds_sales_daily
1. Создание источника:
   ```sql
   SELECT
     d,
     city,
     event_id,
     tickets_sold,
     revenue,
     currency,
     _loaded_at
   FROM bi.v_sales_daily
   ```

2. Поля:
   - **Dimensions:** `d` (Date), `city` (String), `event_id` (String), `currency` (String)
   - **Measures:** `tickets_sold` (SUM), `revenue` (SUM)
   - **Calculated:** `avg_ticket = revenue / nullIf(tickets_sold, 0)`

#### Источник ds_vk_ads_daily
1. Создание источника:
   ```sql
   SELECT
     d,
     city,
     impressions,
     clicks,
     spend,
     _loaded_at
   FROM bi.v_vk_ads_daily
   ```

2. Поля:
   - **Dimensions:** `d` (Date), `city` (String)
   - **Measures:** `impressions` (SUM), `clicks` (SUM), `spend` (SUM)
   - **Calculated:** `ctr = clicks / nullIf(impressions,0)`

#### Источник ds_roi_daily
1. Создание источника:
   ```sql
   SELECT
     d,
     city,
     revenue,
     tickets_sold,
     impressions,
     clicks,
     spend,
     roas,
     cpc,
     cpt,
     _loaded_at
   FROM bi.v_marketing_roi_daily
   ```

2. Поля:
   - **Dimensions:** `d`, `city`
   - **Measures:** `revenue`, `tickets_sold`, `impressions`, `clicks`, `spend`
   - **Calculated:** `roas`, `cpc`, `cpt`

#### Источник ds_ops_freshness
1. Создание источника:
   ```sql
   SELECT
     d,
     source,
     loaded_at_sales,
     loaded_at_vk,
     freshness_hours_sales,
     freshness_hours_vk
   FROM bi.v_ops_freshness
   ```

2. Поля:
   - **Dimensions:** `d`, `source`
   - **Measures:** `freshness_hours_sales`, `freshness_hours_vk`

### Дашборды BI-пакета

#### 1. Sales Overview
1. **Фильтры:**
   - Период (диапазон дат)
   - Город (мультиселект)
   - Событие

2. **KPI-виджеты:**
   - Revenue за период (SUM)
   - Tickets за период (SUM)
   - Avg Ticket = revenue / nullIf(tickets_sold, 0)

3. **Визуализации:**
   - Линия: Revenue по дням
   - Столбцы: Tickets по городам (Top-20)
   - Таблица: деталь по `city, event_id, d`

#### 2. Marketing ROI
1. **Фильтры:**
   - Период (диапазон дат)
   - Город (мультиселект)

2. **KPI-виджеты:**
   - ROAS за период
   - Spend за период
   - Revenue from Ads за период

3. **Визуализации:**
   - Комбо-график: `Spend` + `Revenue`
   - Линия: ROAS по дням
   - Таблица: `city, d, spend, revenue, roas, cpc, cpt, clicks, impressions`

#### 3. City Performance
1. **Фильтры:**
   - Период (диапазон дат)

2. **Визуализации:**
   - Карта/heatmap городов (если доступна) или Pareto: `Revenue` vs `Spend`, размер = `Tickets`
   - Лестница городов по ROAS (Top/Bottom-10)
   - Срез по событиям в городе (таблица)

#### 4. Ops & Data Quality
1. **Фильтры:**
   - Период (диапазон дат)

2. **KPI-виджеты:**
   - Freshness Sales (часы)
   - Freshness VK (часы)

3. **Визуализации:**
   - Линии: `_loaded_at` за 72 часа
   - Таблица: последние 50 прогонов из `meta.etl_runs`

### Настройки производительности

1. **Автообновление:** 15 минут для всех датасетов
2. **Кэширование:** 10-15 минут
3. **Таймзона:** MSK (фиксация в настройках подключения)
4. **Лимиты:** `max_execution_time = 30s`, `max_result_rows = 1e6`

### Доступы и безопасность

1. **Роли в DataLens:**
   - `bi_viewers` - чтение дашбордов
   - `bi_admins` - редактирование дашбордов

2. **Ограничения доступа:**
   - Подключение ClickHouse привязано только к `bi_viewers`/`bi_admins`
   - Доступ только к схеме `bi` для BI-представлений

### Экспорт и документация

1. **Структура BI-пакета:**
   ```
   bi/
   ├── datasets/                # спецификации полей/калькуляций
   ├── dashboards/              # макеты и описания виджетов
   ├── exports/                 # выгрузки из DataLens (json, id)
   └── README.md
   ```

2. **Экспорт дашбордов:**
   - JSON-экспорты сохраняются в `bi/exports/`
   - Идентификаторы дашбордов документируются в `bi/dashboards/*.md`

### Преимущества BI-пакета

- **Стабильные алиасы полей:** Канонизация городов, единые наименования
- **Готовые джойны:** Предварительно объединенные данные для анализа
- **Оптимизированные запросы:** Без `FINAL`, с использованием агрегатов
- **Единая таймзона:** MSK для всех визуализаций
- **Автоматическое обновление:** Настроенные интервалы и кэширование

### Переключение на BI-пакет

Для перехода существующих дашбордов на BI-слой:

1. Создайте новые источники данных на основе `bi.*` представлений
2. Создайте датасеты `ds_sales_daily`, `ds_vk_ads_daily`, `ds_roi_daily`
3. Импортируйте или создайте дашборды из BI-пакета
4. Настройте автообновление и кэширование
5. Предоставьте доступы группам `bi_viewers`/`bi_admins`

### Откат изменений

При необходимости отката:
1. Переключите источники данных на `zakaz.v_*` представления
2. Скрыть публикацию новых дашбордов
3. Восстановить доступы к предыдущим объектам

### Мониторинг производительности

Для контроля производительности BI-пакета:

```sql
-- Проверка производительности представлений
SELECT
  view_name,
  query_duration_ms,
  read_rows,
  read_bytes
FROM system.query_log
WHERE query LIKE 'bi.v_%'
  AND event_date = today()
ORDER BY query_duration_ms DESC;
```