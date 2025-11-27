# Проверка изменений (UTM, ROMI, Plan) и данных из QTickets API

Цель: быстро убедиться, что новые поля/таблицы работают, данные приходят из QTickets и годны для витрин.

## 1. Предварительно
- ClickHouse поднят (docker-compose из `infra/clickhouse`).
- Есть рабочий `.env.qtickets_api` (DRY_RUN можно оставить true для схемы, false для реальной загрузки).
- `clickhouse-client` доступен (или `docker exec ch-zakaz clickhouse-client ...`).

## 2. Накат схемы
```bash
# в корне dashboard-mvp
clickhouse-client -n < infra/clickhouse/migrations/2025-qtickets-api-utm-plan.sql
clickhouse-client -q "SHOW COLUMNS FROM zakaz.stg_qtickets_api_orders_raw"
```
Убедиться, что есть `utm_source/utm_medium/utm_campaign/utm_content/utm_term/payload_json`, таблицы `fact_qtickets_sales_utm_daily`, `plan_sales`, view `v_romi_daily`, `v_plan_vs_fact`.

## 3. Запуск загрузчика QTickets (с UTM)
```bash
python -m integrations.qtickets_api.loader \
  --envfile secrets/.env.qtickets_api \
  --since-hours 24 \
  --verbose
```
Ожидание: в логах видно orders>0, `sales_utm_daily_rows` > 0. При DRY_RUN=false данные пишутся.

## 4. Мини-квест по ClickHouse
```sql
-- UTM покрытие за 7 дней
SELECT count() AS orders_last_7d,
       sum(utm_source='' OR utm_source IS NULL) AS without_utm,
       round(if(count()=0,0,without_utm*100.0/count()),2) AS pct_without_utm
FROM zakaz.stg_qtickets_api_orders_raw
WHERE sale_ts >= now() - INTERVAL 7 DAY;

-- Агрегат по UTM
SELECT * FROM zakaz.v_qtickets_sales_utm_daily ORDER BY d DESC LIMIT 10;

-- ROMI view (выручка + spend)
SELECT * FROM zakaz.v_romi_daily ORDER BY d DESC LIMIT 10;
```

## 5. Проверка плана
```bash
# CSV с колонками: sales_date,event_id,city,plan_tickets,plan_revenue
python -m ch-python.loader.plan_sales_loader \
  --csv ./plan_sample.csv \
  --envfile infra/clickhouse/.env
```
Потом:
```sql
SELECT * FROM zakaz.v_plan_vs_fact ORDER BY sales_date DESC LIMIT 10;
```

## 6. Smoke-проверки
```bash
clickhouse-client -n < infra/clickhouse/smoke_checks_qtickets_api.sql
```
Следить за `orders_without_utm` и свежестью таблиц.

## 7. Быстрый sanity по API данным
- В логах загрузчика убедиться, что `orders` > 0, `sales_rows` > 0.
- Если UTM пустые: проверить сырой `payload_json` в `stg_qtickets_api_orders_raw`.

## 8. DataLens (после обновления источников)
- Подтянуть новые view в датасетах:
  - Продажи: `v_qtickets_sales_utm_daily` (поле utm_group для unknown).
  - ROMI: `v_romi_daily` (`bi/datasets/ds_romi_daily.yaml`).
  - План/факт: `v_plan_vs_fact` (`bi/datasets/ds_plan_vs_fact.yaml`).
- Проверить плитки: выручка, билеты, unknown, spend VK/Direct, ROAS, план/факт.

## 9. Если что-то не так
- Нет данных в `fact_qtickets_sales_utm_daily`: заказам не хватает UTM или они в другом поле — смотрим `payload_json`.
- Ошибки на price-shades/barcodes/seats: включить скипы `QTICKETS_SKIP_PRICE_SHADES=true`, `QTICKETS_SKIP_BARCODES=true`, `QTICKETS_SKIP_INVENTORY=true`.
- Нет расходов в ROMI: проверить, что `fact_vk_ads_daily`/`fact_direct_daily` заполнены и UTM совпадают.
- Проблемы с promo_codes: выполнить hotfix миграцию `infra/clickhouse/migrations/2025-qtickets-api-promo-hotfix.sql`.
