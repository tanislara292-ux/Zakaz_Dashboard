# Техническая спецификация DataLens для Zakaz Dashboard

## Обзор

Документ содержит технические спецификации для настройки подключений, источников данных, датасетов и дашбордов в Yandex DataLens для проекта Zakaz Dashboard.

## Спецификация подключения к ClickHouse

### Параметры подключения

```yaml
connection:
  name: ch_zakaz_prod
  type: ClickHouse
  host: bi.zakaz-dashboard.ru
  port: 443
  database: zakaz
  username: datalens_reader
  password: DataLens2024!Strong#Pass
  use_https: true
  cache_ttl: 300  # 5 минут
```

### Проверка подключения

```sql
-- Тестовый запрос для проверки подключения
SELECT 1 as test_connection;

-- Проверка доступных таблиц
SHOW TABLES FROM zakaz;
```

## Спецификации источников данных

### Источник: src_ch_sales_latest

```yaml
source:
  name: src_ch_sales_latest
  connection: ch_zakaz_prod
  type: SQL
  query: |
    SELECT
        event_date,
        city,
        event_name,
        tickets_sold,
        revenue,
        refunds_amount,
        (revenue - refunds_amount) AS net_revenue
    FROM zakaz.v_sales_latest
  cache_ttl: 600  # 10 минут
```

### Источник: src_ch_marketing_daily

```yaml
source:
  name: src_ch_marketing_daily
  connection: ch_zakaz_prod
  type: SQL
  query: |
    SELECT
        d,
        city,
        spend_total,
        net_revenue,
        romi
    FROM zakaz.v_marketing_daily
  cache_ttl: 600  # 10 минут
```

### Источник: src_ch_sales_14d

```yaml
source:
  name: src_ch_sales_14d
  connection: ch_zakaz_prod
  type: SQL
  query: |
    SELECT
        d AS event_date,
        city,
        tickets,
        net_revenue
    FROM zakaz.v_sales_14d
  cache_ttl: 300  # 5 минут
```

## Спецификации датасетов

### Датасет: ds_sales

```yaml
dataset:
  name: ds_sales
  source: src_ch_sales_latest
  fields:
    - name: event_date
      type: Date
      title: Дата мероприятия
      format: YYYY-MM-DD
      timezone: Europe/Moscow
      
    - name: city
      type: String
      title: Город
      
    - name: event_name
      type: String
      title: Мероприятие
      
    - name: tickets_sold
      type: Integer
      title: Продано билетов
      aggregation: SUM
      
    - name: revenue
      type: Decimal
      title: Выручка
      aggregation: SUM
      format: "#,##0.00 ₽"
      
    - name: refunds_amount
      type: Decimal
      title: Возвраты
      aggregation: SUM
      format: "#,##0.00 ₽"
      
    - name: net_revenue
      type: Decimal
      title: Чистая выручка
      aggregation: SUM
      format: "#,##0.00 ₽"
      
  calculated_fields:
    - name: avg_ticket
      title: Средний чек
      formula: revenue / nullIf(tickets_sold, 0)
      type: Decimal
      format: "#,##0.00 ₽"
      
    - name: week
      title: Неделя
      formula: toWeek(event_date)
      type: Integer
      
    - name: month
      title: Месяц
      formula: toMonth(event_date)
      type: Integer
      
  default_filters:
    - field: event_date
      operator: between
      value: "today() - 30, today()"
```

### Датасет: ds_marketing

```yaml
dataset:
  name: ds_marketing
  source: src_ch_marketing_daily
  fields:
    - name: d
      type: Date
      title: Дата
      format: YYYY-MM-DD
      timezone: Europe/Moscow
      
    - name: city
      type: String
      title: Город
      
    - name: spend_total
      type: Decimal
      title: Расходы
      aggregation: SUM
      format: "#,##0.00 ₽"
      
    - name: net_revenue
      type: Decimal
      title: Доход
      aggregation: SUM
      format: "#,##0.00 ₽"
      
    - name: romi
      type: Decimal
      title: ROMI
      aggregation: AVG
      format: "#,##0.00"
      
  calculated_fields:
    - name: roas
      title: ROAS
      formula: net_revenue / nullIf(spend_total, 0)
      type: Decimal
      format: "#,##0.00"
      
  default_filters:
    - field: d
      operator: between
      value: "today() - 30, today()"
```

### Датасет: ds_sales_14d

```yaml
dataset:
  name: ds_sales_14d
  source: src_ch_sales_14d
  fields:
    - name: event_date
      type: Date
      title: Дата
      format: YYYY-MM-DD
      timezone: Europe/Moscow
      
    - name: city
      type: String
      title: Город
      
    - name: tickets
      type: Integer
      title: Билеты
      aggregation: SUM
      
    - name: net_revenue
      type: Decimal
      title: Выручка
      aggregation: SUM
      format: "#,##0.00 ₽"
      
  calculated_fields:
    - name: avg_ticket
      title: Средний чек
      formula: net_revenue / nullIf(tickets, 0)
      type: Decimal
      format: "#,##0.00 ₽"
```

## Спецификации дашбордов

### Дашборд: Zakaz: Продажи

```yaml
dashboard:
  name: Zakaz: Продажи
  description: Аналитика продаж билетов
  auto_refresh: 900  # 15 минут
  timezone: Europe/Moscow
  
  filters:
    - name: period
      title: Период
      type: dateRange
      field: event_date
      default: "today() - 30, today()"
      
    - name: cities
      title: Города
      type: multiSelect
      field: city
      
  widgets:
    - name: kpi_revenue
      title: Выручка
      type: indicator
      dataset: ds_sales
      measure: net_revenue
      aggregation: SUM
      format: "#,##0.00 ₽"
      period: "today() - 7, today()"
      position: {x: 0, y: 0, w: 4, h: 2}
      
    - name: kpi_tickets
      title: Продано билетов
      type: indicator
      dataset: ds_sales
      measure: tickets_sold
      aggregation: SUM
      format: "#,##0"
      period: "today() - 7, today()"
      position: {x: 4, y: 0, w: 4, h: 2}
      
    - name: kpi_avg_ticket
      title: Средний чек
      type: indicator
      dataset: ds_sales
      measure: avg_ticket
      aggregation: AVG
      format: "#,##0.00 ₽"
      period: "today() - 7, today()"
      position: {x: 8, y: 0, w: 4, h: 2}
      
    - name: chart_revenue_trend
      title: Динамика выручки
      type: line
      dataset: ds_sales
      x: event_date
      y: net_revenue
      aggregation: SUM
      position: {x: 0, y: 2, w: 8, h: 3}
      
    - name: chart_top_cities
      title: Топ городов по выручке
      type: bar
      dataset: ds_sales
      x: city
      y: net_revenue
      aggregation: SUM
      sort: {field: net_revenue, direction: desc}
      limit: 20
      position: {x: 8, y: 2, w: 4, h: 3}
      
    - name: table_sales_detail
      title: Детализация продаж
      type: table
      dataset: ds_sales
      columns: [event_date, city, event_name, tickets_sold, net_revenue, avg_ticket]
      sort: [{field: event_date, direction: desc}]
      position: {x: 0, y: 5, w: 12, h: 4}
```

### Дашборд: Zakaz: Эффективность рекламы

```yaml
dashboard:
  name: Zakaz: Эффективность рекламы
  description: Аналитика эффективности рекламных кампаний
  auto_refresh: 900  # 15 минут
  timezone: Europe/Moscow
  
  filters:
    - name: period
      title: Период
      type: dateRange
      field: d
      default: "today() - 30, today()"
      
    - name: cities
      title: Города
      type: multiSelect
      field: city
      
  widgets:
    - name: kpi_roas
      title: ROAS
      type: indicator
      dataset: ds_marketing
      measure: roas
      aggregation: AVG
      format: "#,##0.00"
      color_conditions:
        - {value: "> 1.5", color: "green"}
        - {value: ">= 1 AND <= 1.5", color: "yellow"}
        - {value: "< 1", color: "red"}
      position: {x: 0, y: 0, w: 4, h: 2}
      
    - name: kpi_spend
      title: Расходы
      type: indicator
      dataset: ds_marketing
      measure: spend_total
      aggregation: SUM
      format: "#,##0.00 ₽"
      position: {x: 4, y: 0, w: 4, h: 2}
      
    - name: kpi_revenue
      title: Доход
      type: indicator
      dataset: ds_marketing
      measure: net_revenue
      aggregation: SUM
      format: "#,##0.00 ₽"
      position: {x: 8, y: 0, w: 4, h: 2}
      
    - name: chart_roas_by_city
      title: ROAS по городам
      type: bar
      dataset: ds_marketing
      x: city
      y: romi
      aggregation: AVG
      color_conditions:
        - {value: "> 1.5", color: "green"}
        - {value: ">= 1 AND <= 1.5", color: "yellow"}
        - {value: "< 1", color: "red"}
      sort: {field: romi, direction: desc}
      position: {x: 0, y: 2, w: 6, h: 3}
      
    - name: chart_spend_revenue
      title: Расходы и доходы
      type: combo
      dataset: ds_marketing
      x: d
      y_left: spend_total
      y_right: net_revenue
      aggregation: SUM
      position: {x: 6, y: 2, w: 6, h: 3}
      
    - name: table_marketing_detail
      title: Детализация по рекламе
      type: table
      dataset: ds_marketing
      columns: [d, city, spend_total, net_revenue, romi, roas]
      sort: [{field: d, direction: desc}]
      position: {x: 0, y: 5, w: 12, h: 4}
```

## Настройки производительности

### Оптимизация запросов

```yaml
performance:
  query_timeout: 30  # секунд
  max_result_rows: 1000000
  cache_ttl:
    fast_queries: 300  # 5 минут
    slow_queries: 600  # 10 минут
    
  materialized_views:
    - name: v_sales_14d
      description: Агрегированные данные за 14 дней для быстрых графиков
      refresh_interval: 3600  # 1 час
```

### Настройки кэширования

```yaml
caching:
  connection_cache: 300  # 5 минут
  source_cache: 600  # 10 минут
  dataset_cache: 900  # 15 минут
  dashboard_cache: 900  # 15 минут
```

## Мониторинг и алерты

### Метрики производительности

```yaml
monitoring:
  metrics:
    - name: query_execution_time
      threshold: 5000  # мс
      alert_type: warning
      
    - name: dashboard_load_time
      threshold: 10000  # мс
      alert_type: error
      
    - name: data_freshness
      threshold: 7200  # секунды (2 часа)
      alert_type: error
```

### Проверки качества данных

```sql
-- Проверка свежести данных
SELECT 
    'sales' as source,
    max(event_date) as latest_date,
    today() - max(event_date) as days_behind
FROM zakaz.v_sales_latest

UNION ALL

SELECT 
    'marketing' as source,
    max(d) as latest_date,
    today() - max(d) as days_behind
FROM zakaz.v_marketing_daily;

-- Проверка на дубликаты
SELECT 
    count() - countDistinct(concat(event_date, city, event_name)) as duplicates
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7;

-- Проверка полноты данных
SELECT 
    event_date,
    count(DISTINCT city) as cities_count,
    sum(tickets_sold) as total_tickets,
    sum(revenue) as total_revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7
GROUP BY event_date
ORDER BY event_date;
```

## Безопасность и права доступа

### Роли в DataLens

```yaml
roles:
  - name: bi_viewers
    permissions:
      - read: dashboards
      - read: datasets
      - read: connections
      
  - name: bi_admins
    permissions:
      - read: dashboards
      - write: dashboards
      - read: datasets
      - write: datasets
      - read: connections
      - write: connections
```

### Ограничения доступа

```yaml
access_restrictions:
  - resource: connections
    allowed_roles: [bi_admins]
    
  - resource: datasets
    allowed_roles: [bi_viewers, bi_admins]
    
  - resource: dashboards
    allowed_roles: [bi_viewers, bi_admins]
```

## Резервное копирование и восстановление

### Экспорт конфигурации

```yaml
backup:
  frequency: daily
  retention: 30 days
  objects:
    - connections
    - datasets
    - dashboards
    
  export_format: json
  storage: s3://datalens-backups/zakaz/
```

### Процедура восстановления

```bash
# Восстановление подключения
datalens-cli connection import --file ch_zakaz_prod.json

# Восстановление датасетов
datalens-cli dataset import --file ds_sales.json
datalens-cli dataset import --file ds_marketing.json

# Восстановление дашбордов
datalens-cli dashboard import --file sales_dashboard.json
datalens-cli dashboard import --file marketing_dashboard.json
```

---

**Версия**: 1.0.0
**Дата обновления**: $(date +%Y-%m-%d)