# BI-пакет для Zakaz Dashboard

## Обзор

Этот каталог содержит BI-пакет для проекта Zakaz, включающий датасеты и дашборды для DataLens на основе данных ClickHouse.

## Структура

```
bi/
├── datasets/                # спецификации полей/калькуляций (yaml/md)
├── dashboards/              # макеты и описания виджетов (md)
├── exports/                 # выгрузки из DataLens (json, id-шники)
└── README.md
```

## Источники данных

BI-пакет использует следующие представления из ClickHouse:

- `bi.v_sales_daily` — продажи с канонизацией городов
- `bi.v_vk_ads_daily` — маркетинговые метрики по городам/дате
- `bi.v_marketing_roi_daily` — join продаж и расходов (ROAS, CPC, CPT)
- `bi.v_ops_freshness` — свежесть и последние прогонки из `meta.*`

## Датасеты DataLens

### ds_sales_daily
- **Источник:** `bi.v_sales_daily`
- **Поля:** `d` (Date), `city` (Dim), `event_id` (Dim), `tickets_sold` (Measure: SUM), `revenue` (Measure: SUM), `currency` (Dim)
- **Вычисляемые:** `avg_ticket = revenue / nullIf(tickets_sold, 0)`

### ds_vk_ads_daily
- **Источник:** `bi.v_vk_ads_daily`
- **Поля:** `d`, `city`, `impressions` (SUM), `clicks` (SUM), `spend` (SUM)
- **Вычисляемые:** `ctr = clicks / nullIf(impressions,0)`

### ds_roi_daily
- **Источник:** `bi.v_marketing_roi_daily`
- **Поля:** `d`, `city`, `revenue`, `tickets_sold`, `impressions`, `clicks`, `spend`, `roas`, `cpc`, `cpt`

## Дашборды

### 1. Sales Overview
- **Фильтры:** период (дата), город (multi), событие
- **KPI:** `Revenue`, `Tickets`, `Avg Ticket`
- **Визуализации:** Revenue по дням, Tickets по городам (Top-20)
- **Таблица:** деталь по `city, event_id, d`

### 2. Marketing ROI
- **Фильтры:** период, город
- **KPI:** `ROAS`, `Spend`, `Revenue from Ads`
- **Визуализации:** `Spend` + `Revenue` (комбо-график)
- **Таблица:** `city, d, spend, revenue, roas, cpc, cpt, clicks, impressions`

### 3. City Performance
- **Визуализации:** Карта/heatmap городов или Pareto: `Revenue` vs `Spend`
- **Сортировка:** Лестница городов по ROAS (Top/Bottom-10)
- **Детализация:** Срез по событиям в городе (таблица)

### 4. Ops & Data Quality
- **KPI:** «Freshness Sales (часы)», «Freshness VK (часы)»
- **Визуализации:** `_loaded_at` за 72 часа
- **Таблица:** последние 50 прогонов из `meta.etl_runs`

## Настройки производительности

- Автообновление DataLens: интервал 15 минут
- Кэш: 10–15 минут
- Таймзона: MSK
- Лимиты: `max_execution_time = 30s`, `max_result_rows = 1e6`

## Доступы

- Роли в DataLens: `bi_viewers` (чтение), `bi_admins` (редактирование)
- Подключение ClickHouse привязано только к `bi_viewers`/`bi_admins`

## Экспорт

Идентификаторы и экспорты дашбордов сохраняются в каталоге `exports/`.