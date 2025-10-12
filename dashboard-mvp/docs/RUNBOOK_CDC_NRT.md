# RUNBOOK: CDC и Near-Real-Time (NRT) обновления

## Обзор

Этот документ описывает систему инкрементальных CDC-загрузок и near-real-time обновлений витрин `dm_sales_daily` и `dm_vk_ads_daily`.

## Компоненты системы

### 1. CDC загрузчики

#### `qtickets_cdc.py`
Инкрементальный загрузчик для QTickets API.

**Особенности:**
- Использует водяные знаки (watermarks) для отслеживания обработанных данных
- Загружает изменения за скользящее окно (D-3...сейчас) с перекрытием
- Поддерживает операции UPSERT/DELETE
- Пишет в стейджинг `zakaz.stg_sales_events`

**Запуск:**
```bash
python ch-python/cli.py cdc-qtickets --minutes 10
```

#### `vk_ads_cdc.py`
Инкрементальный загрузчик для VK Ads API.

**Особенности:**
- Учитывает лаги данных VK Ads (статистика дозревает)
- Загружает за окно D-3...D-0 по датам отчётности
- Пишет в стейджинг `zakaz.stg_vk_ads_daily`

**Запуск:**
```bash
python ch-python/cli.py cdc-vk --minutes 10
```

### 2. Инкрементальные билдеры витрин

#### `build_dm_sales_incr.py`
Инкрементальный билдер витрины продаж.

**Алгоритм:**
1. Определяет затронутые даты на основе `_loaded_at` в стейджинге
2. Для каждой даты:
   - Определяет активные ключи (последний `_op = 'UPSERT'`)
   - Удаляет существующие данные за дату
   - Вставляет агрегированные данные только для активных ключей

**Запуск:**
```bash
python ch-python/cli.py build-dm-sales-incr --calculate-sli
```

#### `build_dm_vk_incr.py`
Инкрементальный билдер витрины VK Ads.

**Алгоритм:**
Аналогичен билдеру продаж, но с учетом специфики VK Ads.

**Запуск:**
```bash
python ch-python/cli.py build-dm-vk-incr --calculate-sli
```

### 3. Оркестрация NRT

#### systemd таймеры

| Таймер | Описание | Сдвиг |
|--------|----------|-------|
| `etl@cdc_qtickets.timer` | Загрузка QTickets CDC | 0 мин |
| `etl@cdc_vk.timer` | Загрузка VK Ads CDC | 0 мин |
| `etl@build_dm_sales_incr.timer` | Построение витрины продаж | +2 мин |
| `etl@build_dm_vk_incr.timer` | Построение витрины VK Ads | +4 мин |

**Установка:**
```bash
sudo cp infra/systemd/etl@cdc_*.service /etc/systemd/system/
sudo cp infra/systemd/etl@cdc_*.timer /etc/systemd/system/
sudo cp infra/systemd/etl@build_*_incr.service /etc/systemd/system/
sudo cp infra/systemd/etl@build_*_incr.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now etl@cdc_qtickets.timer
sudo systemctl enable --now etl@cdc_vk.timer
sudo systemctl enable --now etl@build_dm_sales_incr.timer
sudo systemctl enable --now etl@build_dm_vk_incr.timer
```

### 4. Мониторинг качества данных

#### `quality_sli.py`
Расчет SLI показателей качества данных.

**Метрики:**
- `freshness_hours` - свежесть данных в часах
- `completeness_ratio` - полнота данных (0-1)
- `latency_hours` - задержка обработки в часах

**Запуск:**
```bash
python ops/quality_sli.py --days 3
```

#### `slo_guard.py`
Мониторинг SLO и отправка алертов.

**SLO пороги:**
- Свежесть продаж сегодня: ≤ 2 часа
- Свежесть VK Ads сегодня: ≤ 3 часа
- Полнота продаж сегодня: ≥ 95%
- Полнота VK Ads сегодня: ≥ 90%

**Запуск:**
```bash
python ops/slo_guard.py --check
```

## Процедуры

### Запуск NRT цикла вручную

```bash
# Шаг 1: Загрузка CDC
bash ops/run_job.sh cdc_qtickets
bash ops/run_job.sh cdc_vk

# Шаг 2: Построение витрин
bash ops/run_job.sh build_dm_sales_incr
bash ops/run_job.sh build_dm_vk_incr

# Шаг 3: Расчет SLI
python ops/quality_sli.py --days 1

# Шаг 4: Проверка SLO
python ops/slo_guard.py --check
```

### Проверка статуса NRT

```bash
# Проверка таймеров
systemctl list-timers | grep etl@

# Просмотр логов
journalctl -u etl@cdc_qtickets.service -f
journalctl -u etl@build_dm_sales_incr.service -f

# Проверка водяных знаков
clickhouse-client --query "SELECT * FROM meta.watermarks ORDER BY updated_at DESC LIMIT 10"

# Проверка свежести данных
python ops/slo_guard.py --status --json
```

### Диагностика проблем

#### Нет данных в стейджинге

1. Проверьте работу CDC загрузчиков:
```bash
journalctl -u etl@cdc_qtickets.service -n 50
```

2. Проверьте водяные знаки:
```sql
SELECT * FROM meta.watermarks WHERE source = 'qtickets';
```

3. Запустите загрузчик вручную с отладкой:
```bash
python ch-python/cli.py cdc-qtickets --verbose
```

#### Данные есть в стейджинге, но не в витрине

1. Проверьте работу билдеров:
```bash
journalctl -u etl@build_dm_sales_incr.service -n 50
```

2. Проверьте наличие затронутых дат:
```sql
SELECT DISTINCT event_date FROM zakaz.stg_sales_events 
WHERE event_date >= today() - 3 ORDER BY event_date DESC;
```

3. Запустите билдер вручную:
```bash
python ch-python/cli.py build-dm-sales-incr --verbose
```

#### Нарушения SLO

1. Проверьте SLI значения:
```sql
SELECT * FROM meta.sli_daily WHERE d >= today() - 1 ORDER BY d DESC;
```

2. Проверьте алерты:
```sql
SELECT * FROM meta.etl_alerts ORDER BY ts DESC LIMIT 10;
```

3. Проверьте настройки порогов в `ops/slo_guard.py`

### Backfill для CDC

Для полной перезагрузки данных за период:

1. Сбросьте водяные знаки:
```sql
DELETE FROM meta.watermarks WHERE source = 'qtickets';
DELETE FROM meta.watermarks WHERE source = 'vk_ads';
```

2. Очистите стейджинг:
```sql
ALTER TABLE zakaz.stg_sales_events DELETE WHERE event_date >= '2025-10-01';
ALTER TABLE zakaz.stg_vk_ads_daily DELETE WHERE stat_date >= '2025-10-01';
```

3. Запустите загрузчики с расширенным окном:
```bash
python ch-python/cli.py cdc-qtickets --minutes 1440  # 24 часа
python ch-python/cli.py cdc-vk --minutes 1440
```

## Обслуживание

### Изменение интервала NRT

1. Отредактируйте `.env`:
```bash
NRT_INTERVAL_MIN=5  # изменить на 5 минут
```

2. Перезапустите таймеры:
```bash
sudo systemctl daemon-reload
sudo systemctl restart etl@cdc_qtickets.timer
sudo systemctl restart etl@cdc_vk.timer
sudo systemctl restart etl@build_dm_sales_incr.timer
sudo systemctl restart etl@build_dm_vk_incr.timer
```

### Изменение окна CDC

1. Отредактируйте `.env`:
```bash
CDC_WINDOW_DAYS=5  # расширить до 5 дней
SAFETY_LAG_MIN=60  # увеличить лаг безопасности
```

2. Перезапустите сервисы:
```bash
sudo systemctl restart etl@cdc_qtickets.service
sudo systemctl restart etl@cdc_vk.service
```

### Очистка старых данных

Стейджинги автоматически очищаются по TTL (30 дней). Для ручной очистки:

```sql
-- Очистка стейджингов
ALTER TABLE zakaz.stg_sales_events DELETE WHERE _loaded_at < today() - 30;
ALTER TABLE zakaz.stg_vk_ads_daily DELETE WHERE _loaded_at < today() - 30;

-- Очистка метаданных
ALTER TABLE meta.sli_daily DELETE WHERE d < today() - 90;
ALTER TABLE meta.etl_runs DELETE WHERE started_at < today() - 90;
```

## Отказ и восстановление

### Отключение NRT

```bash
sudo systemctl disable --now etl@cdc_qtickets.timer
sudo systemctl disable --now etl@cdc_vk.timer
sudo systemctl disable --now etl@build_dm_sales_incr.timer
sudo systemctl disable --now etl@build_dm_vk_incr.timer
```

### Возврат к суточным батчам

1. Отключите NRT таймеры (см. выше)
2. Включите старые таймеры:
```bash
sudo systemctl enable --now etl@build_dm_sales.timer
sudo systemctl enable --now etl@build_dm_vk.timer
```

3. Настройте расписание для суточных загрузок в EPIC-CH-04

### Восстановление после сбоя

1. Определите последнюю успешную загрузку:
```sql
SELECT job, started_at, status, rows_written 
FROM meta.etl_runs 
WHERE job LIKE '%cdc%' OR job LIKE '%incr%'
ORDER BY started_at DESC LIMIT 10;
```

2. Восстановите водяные знаки:
```sql
INSERT INTO meta.watermarks (source, stream, wm_type, wm_value_s, updated_at)
VALUES ('qtickets', 'orders', 'updated_at', '2025-10-10T12:00:00', now());
```

3. Запустите NRT цикл вручную для догрузки

## Мониторинг в DataLens

### Датасеты для мониторинга

1. **Свежесть данных** - на основе `meta.sli_daily`
   - График `freshness_hours` по датам
   - Фильтр по таблицам (`dm_sales_daily`, `dm_vk_ads_daily`)

2. **Статус прогонов** - на основе `meta.etl_runs`
   - Временная шкала прогонов
   - Статусы (ok/error)
   - Длительность выполнения

3. **Алерты** - на основе `meta.etl_alerts`
   - Таблица последних алертов
   - График количества алертов по времени

### Виджеты для дашборда

1. **KPI Свежесть сегодня**
   - Sales: `last_value(freshness_hours) WHERE table_name = 'dm_sales_daily'`
   - VK Ads: `last_value(freshness_hours) WHERE table_name = 'dm_vk_ads_daily'`

2. **Последние прогоны**
   - Таблица с последними 20 запусками NRT циклов

3. **Обновления за 72 часа**
   - График `_loaded_at` из витрин

4. **SLO Status**
   - Индикаторы соблюдения SLO по основным метрикам