# Статус интеграций и руководство по проверке

## Обзор

Документ содержит информацию о текущем статусе интеграций с источниками данных (QTickets, VK Ads, Яндекс.Директ) и инструкции по их проверке и запуску.

## Текущий статус интеграций

### ✅ Что реализовано

1. **Полные загрузчики для всех источников**:
   - `integrations/qtickets/loader.py` - Загрузчик данных QTickets API
   - `integrations/vk_ads/loader.py` - Загрузчик данных VK Ads API
   - `integrations/direct/loader.py` - Загрузчик данных Яндекс.Директ API

2. **Архитектура данных**:
   - Сырые таблицы для всех источников
   - Агрегированные таблицы для быстрой отчетов
   - Представления для DataLens

3. **Автоматизация**:
   - Systemd таймеры для периодической загрузки
   - Логирование и метаданные о запусках
   - Обработка ошибок

### ❌ Что требует проверки

1. **Наличие токенов API**:
   - QTickets_TOKEN
   - VK_TOKEN
   - DIRECT_LOGIN и DIRECT_TOKEN

2. **Работоспособность интеграций**:
   - Доступность API endpoints
   - Корректность ответов
   - Загрузка данных в ClickHouse

## Проверка наличия токенов

### Шаг 1: Проверка файлов конфигурации

```bash
# Проверка наличия файлов с токенами
ls -la secrets/
```

Ожидаемые файлы:
- `secrets/.env.qtickets`
- `secrets/.env.vk`
- `secrets/.env.direct`

### Шаг 2: Проверка содержимого файлов

```bash
# Проверка QTickets токена
grep QTICKETS_TOKEN secrets/.env.qtickets

# Проверка VK токена
grep VK_TOKEN secrets/.env.vk

# Проверка Яндекс.Директ токенов
grep -E "DIRECT_LOGIN|DIRECT_TOKEN" secrets/.env.direct
```

### Шаг 3: Создание файлов с токенами (если отсутствуют)

Если файлы отсутствуют, создайте их на основе шаблонов:

```bash
# Создание файла для QTickets
cp configs/.env.qtickets.sample secrets/.env.qtickets

# Создание файла для VK Ads
cp configs/.env.vk.sample secrets/.env.vk

# Создание файла для Яндекс.Директ
cp configs/.env.direct.sample secrets/.env.direct
```

## Запуск интеграций

### 1. Запуск QTickets загрузчика

```bash
# Запуск загрузчика QTickets
cd dashboard-mvp
python3 integrations/qtickets/loader.py --env secrets/.env.qtickets --days 7

# Проверка результатов
docker exec ch-zakaz clickhouse-client --database=zakaz --query "SELECT count() FROM stg_qtickets_sales_raw"
```

### 2. Запуск VK Ads загрузчика

```bash
# Запуск загрузчика VK Ads
cd dashboard-mvp
python3 integrations/vk_ads/loader.py --env secrets/.env.vk --days 7

# Проверка результатов
docker exec ch-zakaz clickhouse-client --database=zakaz --query "SELECT count() FROM fact_vk_ads_daily"
```

### 3. Запуск Яндекс.Директ загрузчика

```bash
# Запуск загрузчика Яндекс.Директ
cd dashboard-mvp
python3 integrations/direct/loader.py --env secrets/.env.direct --days 7

# Проверка результатов
docker exec ch-zakaz clickhouse-client --database=zakaz --query "SELECT count() FROM fact_direct_daily"
```

## Проверка данных в ClickHouse

### Проверка свежести данных

```sql
-- Проверка свежести данных QTickets
SELECT 
    'qtickets' as source,
    max(event_date) as latest_date,
    today() - max(event_date) as days_behind
FROM zakaz.stg_qtickets_sales_raw;

-- Проверка свежести данных VK Ads
SELECT 
    'vk_ads' as source,
    max(stat_date) as latest_date,
    today() - max(stat_date) as days_behind
FROM zakaz.fact_vk_ads_daily;

-- Проверка свежести данных Яндекс.Директ
SELECT 
    'direct' as source,
    max(stat_date) as latest_date,
    today() - max(stat_date) as days_behind
FROM zakaz.fact_direct_daily;
```

### Проверка качества данных

```sql
-- Проверка на дубликаты в данных продаж
SELECT 
    count() - countDistinct(concat(event_date, city, event_name)) as duplicates
FROM zakaz.stg_qtickets_sales_raw
WHERE event_date >= today() - 7;

-- Проверка полноты данных
SELECT 
    event_date,
    count(DISTINCT city) as cities_count,
    sum(tickets_sold) as total_tickets,
    sum(revenue) as total_revenue
FROM zakaz.stg_qtickets_sales_raw
WHERE event_date >= today() - 7
GROUP BY event_date
ORDER BY event_date;
```

## Автоматическая загрузка

### Проверка Systemd таймеров

```bash
# Проверка статуса таймеров
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'

# Проверка логов последнего запуска
journalctl -u etl@qtickets.service -n 20
journalctl -u etl@vk_ads.service -n 20
journalctl -u etl@direct.service -n 20
```

### Настройка таймеров (если не настроены)

```bash
# Настройка таймеров
cd dashboard-mvp
bash ops/setup_timers.sh

# Запуск таймеров
sudo systemctl enable etl@qtickets.timer
sudo systemctl enable etl@vk_ads.timer
sudo systemctl enable etl@direct.timer

sudo systemctl start etl@qtickets.timer
sudo systemctl start etl@vk_ads.timer
sudo systemctl start etl@direct.timer
```

## Тестирование интеграций

### Запуск smoke-тестов

```bash
# Запуск smoke-тестов
cd dashboard-mvp
python3 ops/smoke_test_integrations.py --verbose
```

### Ручное тестирование API

```bash
# Тест QTickets API
curl -H "Authorization: Bearer YOUR_QTICKETS_TOKEN" \
     https://api.qtickets.ru/v1/events

# Тест VK Ads API
curl -d "access_token=YOUR_VK_TOKEN&v=5.131&method=users.get" \
     https://api.vk.com/method/

# Тест Яндекс.Директ API
curl -H "Authorization: Bearer YOUR_DIRECT_TOKEN" \
     -H "Client-Login: YOUR_DIRECT_LOGIN" \
     -d '{"method": "get", "params": {"SelectionCriteria": {}}}' \
     https://api.direct.yandex.ru/json/v5/campaigns
```

## Проблемы и решения

### Проблема: Отсутствуют токены API

**Решение:**
1. Получите токены у соответствующих сервисов
2. Создайте файлы `secrets/.env.*` с токенами
3. Заполните файлы согласно шаблонам

### Проблема: API недоступен

**Решение:**
1. Проверьте доступность API endpoints
2. Проверьте срок действия токенов
3. Проверьте сетевые настройки

### Проблема: Данные не загружаются

**Решение:**
1. Проверьте логи загрузчиков
2. Проверьте права доступа к ClickHouse
3. Проверьте структуру таблиц

### Проблема: Данные некорректны

**Решение:**
1. Проверьте формат ответов API
2. Проверьте логику нормализации данных
3. Проверьте типы данных в ClickHouse

## Метаданные о запусках

### Просмотр истории запусков

```sql
-- Просмотр последних запусков
SELECT 
    job,
    started_at,
    finished_at,
    status,
    rows_processed,
    message
FROM zakaz.meta_job_runs
ORDER BY started_at DESC
LIMIT 10;
```

### Просмотр метаданных по конкретному источнику

```sql
-- Метаданные QTickets
SELECT 
    metrics,
    message
FROM zakaz.meta_job_runs
WHERE job = 'qtickets_loader'
ORDER BY started_at DESC
LIMIT 5;
```

## Рекомендации для DataLens

### Источники данных для DataLens

1. **Продажи**:
   ```sql
   SELECT
       event_date,
       city,
       event_name,
       tickets_sold,
       revenue,
       refunds_amount,
       (revenue - refunds_amount) AS net_revenue
   FROM zakaz.v_sales_latest
   ```

2. **Маркетинг VK Ads**:
   ```sql
   SELECT
       d,
       city,
       spend_total,
       net_revenue,
       romi
   FROM zakaz.v_marketing_daily
   WHERE source = 'vk_ads'
   ```

3. **Маркетинг Яндекс.Директ**:
   ```sql
   SELECT
       d,
       city,
       spend_total,
       net_revenue,
       romi
   FROM zakaz.v_marketing_daily
   WHERE source = 'direct'
   ```

### Объединенный маркетинговый источник

```sql
SELECT
    d,
    city,
    source,
    spend_total,
    net_revenue,
    romi
FROM (
    SELECT d, city, 'vk_ads' as source, spend_total, net_revenue, romi
    FROM zakaz.v_marketing_daily
    WHERE source = 'vk_ads'
    
    UNION ALL
    
    SELECT d, city, 'direct' as source, spend_total, net_revenue, romi
    FROM zakaz.v_marketing_daily
    WHERE source = 'direct'
)
ORDER BY d, city, source;
```

## Заключение

### ✅ Что готово

- Полные загрузчики для всех источников
- Архитектура данных в ClickHouse
- Автоматизация через Systemd таймеры
- Логирование и метаданные

### 🔄 Что требует проверки

- Наличие и корректность токенов API
- Работоспособность интеграций
- Загрузка реальных данных

### 📋 План действий

1. **Проверить наличие токенов** в файлах `secrets/.env.*`
2. **Запустить интеграции** для проверки работоспособности
3. **Настроить автоматическую загрузку** через Systemd таймеры
4. **Проверить данные** в ClickHouse
5. **Создать источники данных** в DataLens на основе реальных данных

---

**Статус**: 🟡 Интеграции реализованы, требуют проверки и настройки
**Дата**: 20.10.2025
**Версия**: 1.0.0