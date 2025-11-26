# Проверка изменений (UTM, ROMI, план) и данных из QTickets API

Цель: быстро убедиться, что новые поля/таблицы работают, данные приходят из QTickets и годны для витрин (UTM, ROMI, план).

## 1. Предварительно
- ClickHouse поднят (docker-compose из `infra/clickhouse`).
- Есть рабочий `.env.qtickets_api` (DRY_RUN можно оставить true для схемы, false для реальной загрузки).
- `clickhouse-client` доступен (или `docker exec ch-zakaz clickhouse-client ...`).

## 2. Накат схемы
```bash
# в корне dashboard-mvp
clickhouse-client -n -q "SOURCE infra/clickhouse/migrations/2025-qtickets-api-utm-plan.sql"
clickhouse-client -q "SHOW COLUMNS FROM zakaz.stg_qtickets_api_orders_raw"
```
Убедиться, что появились колонки: `utm_source/utm_medium/utm_campaign/utm_content/utm_term/payload_json`, таблицы `fact_qtickets_sales_utm_daily`, `plan_sales`, view `v_romi_daily`, `v_plan_vs_fact`.

## 3. Запуск загрузчика QTickets (с UTM)
```bash
python -m integrations.qtickets_api.loader \
  --envfile secrets/.env.qtickets_api \
  --since-hours 24 \
  --verbose
```
Ожидание: в логах видно количество orders>0, `sales_utm_daily_rows` > 0 (если в заказах есть UTM). При DRY_RUN=false данные пишутся.

## 4. Мини-квест по ClickHouse
```sql
-- UTM покрытие за 7 дней
SELECT count() AS orders_last_7d,
       sum(utm_source='' OR utm_source IS NULL) AS without_utm,
       round(if(count()=0,0,without_utm*100.0/count()),2) AS pct_without_utm
FROM zakaz.stg_qtickets_api_orders_raw
WHERE sale_ts >= now() - INTERVAL 7 DAY;

-- Агрегат по UTM (должен быть >0 при наличии UTM)
SELECT * FROM zakaz.v_qtickets_sales_utm_daily ORDER BY d DESC LIMIT 10;

-- ROMI view (выручка + spend, может быть NULL если расходов нет)
SELECT * FROM zakaz.v_romi_daily ORDER BY d DESC LIMIT 10;
```

## 5. Проверка плана
```bash
# подготовить CSV с колонками: sales_date,event_id,city,plan_tickets,plan_revenue
python -m ch-python.loader.plan_sales_loader \
  --csv ./plan_sample.csv \
  --envfile infra/clickhouse/.env
```
Потом:
```sql
SELECT * FROM zakaz.v_plan_vs_fact ORDER BY sales_date DESC LIMIT 10;
```
Ожидание: плановые строки появились, дифф рассчитывается (NULL только если нет плана/факта).

## 6. Проверка smoke-чеков
```bash
clickhouse-client -n -q "SOURCE infra/clickhouse/smoke_checks_qtickets_api.sql"
```
Следить за `orders_without_utm` и свежестью таблиц.

## 7. Быстрый sanity по API данным
- В логах загрузчика убедиться, что `orders` > 0, `sales_rows` > 0.
- Если заказов нет или UTM пустые: проверить реальную выдачу `/orders` через `qtickets_debug/orders_probe*.py` или добавить UTM в тестовые заказы.

## 8. DataLens (после обновления источников)
- Подтянуть новые view в датасетах:
  - Продажи: добавить поля `utm_*`, `utm_group` из `v_qtickets_sales_utm_daily`.
  - ROMI: источник `v_romi_daily` (реализация в `bi/datasets/ds_romi_daily.yaml`).
  - План/факт: источник `v_plan_vs_fact` (`bi/datasets/ds_plan_vs_fact.yaml`).
- Проверить плитки: выручка, билеты, unknown, spend VK/Direct, ROAS, план/факт.

## 9. Если что-то не так
- Нет данных в `fact_qtickets_sales_utm_daily`: заказам не хватает UTM или они в другом поле — проверить сырой `payload_json` в `stg_qtickets_api_orders_raw`.
- Нет расходов в ROMI: убедиться, что `fact_vk_ads_daily`/`fact_direct_daily` заполнены (запустить соответствующие ETL).
- План пуст: перепроверь CSV или `plan_sales_loader` лог.
