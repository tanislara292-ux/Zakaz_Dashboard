-- SQL-проверки для настройки DataLens
-- Выполняйте от имени пользователя datalens_reader для проверки прав доступа

-- Проверка 1: Базовая проверка подключения
SELECT 'Connection test' as test, 1 as result;

-- Проверка 2: Доступ к базе данных zakaz
SELECT 'Database access' as test, count(*) as result FROM system.databases WHERE name = 'zakaz';

-- Проверка 3: Доступ к представлениям для DataLens
SELECT 'v_sales_latest access' as test, count(*) as result FROM zakaz.v_sales_latest LIMIT 1;
SELECT 'v_sales_14d access' as test, count(*) as result FROM zakaz.v_sales_14d LIMIT 1;

-- Проверка 4: Проверка данных в представлениях
SELECT 'v_sales_latest data count' as test, count(*) as result FROM zakaz.v_sales_latest;
SELECT 'v_sales_14d data count' as test, count(*) as result FROM zakaz.v_sales_14d;

-- Проверка 5: Проверка агрегаций (как в DataLens)
SELECT 
    'v_sales_latest aggregation test' as test,
    sum(tickets_sold) as total_tickets,
    sum(revenue) as total_revenue,
    sum(refunds_amount) as total_refunds,
    sum(revenue - refunds_amount) as net_revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 30;

-- Проверка 6: Проверка дат последнего обновления
SELECT 
    'Latest dates check' as test,
    max(sale_date) as latest_sale_date,
    max(event_date) as latest_event_date
FROM zakaz.v_sales_latest;

-- Проверка 7: Проверка на дубликаты (должно быть 0)
SELECT 
    'Duplicates check' as test,
    count() - countDistinct(dedup_key) as duplicates_count
FROM zakaz.stg_qtickets_sales;

-- Проверка 8: Тестовый запрос для источника данных DataLens
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
LIMIT 10;

-- Проверка 9: Тестовый запрос для агрегации по городам
SELECT 
    'Top cities by revenue' as test,
    city,
    sum(revenue) as total_revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 30
GROUP BY city
ORDER BY total_revenue DESC
LIMIT 5;

-- Проверка 10: Тестовый запрос для временного ряда
SELECT 
    'Daily revenue trend' as test,
    event_date,
    sum(revenue) as daily_revenue
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 7
GROUP BY event_date
ORDER BY event_date;