-- Smoke-проверки для интеграций
-- Используются для мониторинга работоспособности системы

-- Проверка наличия данных за последние дни
SELECT 'qtickets_sales_freshness' as check_name,
       'OK' as status,
       'QTickets sales data is fresh' as message
FROM zakaz.v_sales_latest
WHERE event_date >= today() - 2
LIMIT 1
UNION ALL
SELECT 'qtickets_sales_freshness' as check_name,
       'ERROR' as status,
       'No QTickets sales data for last 2 days' as message
UNION ALL
SELECT 'vk_ads_freshness' as check_name,
       'OK' as status,
       'VK Ads data is fresh' as message
FROM zakaz.fact_vk_ads_daily
WHERE stat_date >= today() - 2
LIMIT 1
UNION ALL
SELECT 'vk_ads_freshness' as check_name,
       'ERROR' as status,
       'No VK Ads data for last 2 days' as message
UNION ALL
SELECT 'direct_freshness' as check_name,
       'OK' as status,
       'Direct data is fresh' as message
FROM zakaz.fact_direct_daily
WHERE stat_date >= today() - 2
LIMIT 1
UNION ALL
SELECT 'direct_freshness' as check_name,
       'ERROR' as status,
       'No Direct data for last 2 days' as message
UNION ALL
-- Проверка на отсутствие дублей в витринах
SELECT 'qtickets_no_duplicates' as check_name,
       'OK' as status,
       'No duplicates in QTickets sales view' as message
FROM (
  SELECT count() as cnt
  FROM (
    SELECT event_date, city, event_name
    FROM zakaz.v_sales_latest
    GROUP BY event_date, city, event_name
    HAVING count() > 1
  )
)
WHERE cnt = 0
UNION ALL
SELECT 'qtickets_no_duplicates' as check_name,
       'ERROR' as status,
       'Duplicates found in QTickets sales view' as message
UNION ALL
-- Проверка на корректность ROMI расчетов
SELECT 'romi_calculations' as check_name,
       'OK' as status,
       'ROMI calculations are correct' as message
FROM zakaz.v_marketing_daily
WHERE d >= today() - 7
  AND romi IS NOT NULL
  AND romi > 0
LIMIT 1
UNION ALL
SELECT 'romi_calculations' as check_name,
       'ERROR' as status,
       'ROMI calculations are incorrect or missing' as message
UNION ALL
-- Проверка на успешные запуски задач
SELECT 'job_runs_success' as check_name,
       'OK' as status,
       'Jobs are running successfully' as message
FROM zakaz.meta_job_runs
WHERE started_at >= now() - INTERVAL 1 DAY
  AND status = 'success'
GROUP BY job
HAVING count() > 0
LIMIT 1
UNION ALL
SELECT 'job_runs_success' as check_name,
       'ERROR' as status,
       'No successful job runs in last 24 hours' as message
UNION ALL
-- Проверка на отсутствие критичных алертов
SELECT 'no_critical_alerts' as check_name,
       'OK' as status,
       'No critical alerts' as message
FROM zakaz.alerts
WHERE alert_type = 'error'
  AND acknowledged = false
  AND created_at >= now() - INTERVAL 1 DAY
HAVING count() = 0
UNION ALL
SELECT 'no_critical_alerts' as check_name,
       'ERROR' as status,
       'Critical alerts found' as message;

-- Сводка по состоянию системы
SELECT 'system_health' as check_name,
       CASE 
         WHEN error_count = 0 THEN 'OK'
         WHEN error_count <= 2 THEN 'WARNING'
         ELSE 'ERROR'
       END as status,
       concat('System health: ', error_count, ' errors, ', warning_count, ' warnings') as message
FROM (
  SELECT 
    sumIf(status = 'ERROR', 1, 0) as error_count,
    sumIf(status = 'WARNING', 1, 0) as warning_count
  FROM (
    SELECT 'qtickets_sales_freshness' as check_name,
           'OK' as status
    FROM zakaz.v_sales_latest
    WHERE event_date >= today() - 2
    LIMIT 1
    UNION ALL
    SELECT 'qtickets_sales_freshness' as check_name,
           'ERROR' as status
    UNION ALL
    SELECT 'vk_ads_freshness' as check_name,
           'OK' as status
    FROM zakaz.fact_vk_ads_daily
    WHERE stat_date >= today() - 2
    LIMIT 1
    UNION ALL
    SELECT 'vk_ads_freshness' as check_name,
           'ERROR' as status
    UNION ALL
    SELECT 'direct_freshness' as check_name,
           'OK' as status
    FROM zakaz.fact_direct_daily
    WHERE stat_date >= today() - 2
    LIMIT 1
    UNION ALL
    SELECT 'direct_freshness' as check_name,
           'ERROR' as status
    UNION ALL
    SELECT 'qtickets_no_duplicates' as check_name,
           'OK' as status
    FROM (
      SELECT count() as cnt
      FROM (
        SELECT event_date, city, event_name
        FROM zakaz.v_sales_latest
        GROUP BY event_date, city, event_name
        HAVING count() > 1
      )
    )
    WHERE cnt = 0
    UNION ALL
    SELECT 'qtickets_no_duplicates' as check_name,
           'ERROR' as status
    UNION ALL
    SELECT 'romi_calculations' as check_name,
           'OK' as status
    FROM zakaz.v_marketing_daily
    WHERE d >= today() - 7
      AND romi IS NOT NULL
      AND romi > 0
    LIMIT 1
    UNION ALL
    SELECT 'romi_calculations' as check_name,
           'ERROR' as status
    UNION ALL
    SELECT 'job_runs_success' as check_name,
           'OK' as status
    FROM zakaz.meta_job_runs
    WHERE started_at >= now() - INTERVAL 1 DAY
      AND status = 'success'
    GROUP BY job
    HAVING count() > 0
    LIMIT 1
    UNION ALL
    SELECT 'job_runs_success' as check_name,
           'ERROR' as status
    UNION ALL
    SELECT 'no_critical_alerts' as check_name,
           'OK' as status
    FROM zakaz.alerts
    WHERE alert_type = 'error'
      AND acknowledged = false
      AND created_at >= now() - INTERVAL 1 DAY
    HAVING count() = 0
    UNION ALL
    SELECT 'no_critical_alerts' as check_name,
           'ERROR' as status
  ) checks
) summary;