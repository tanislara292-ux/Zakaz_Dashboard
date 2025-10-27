# Архитектура и потоки данных

## 1. Источники и назначения
- **QTickets API** — источник заказов и инвентаря (устаревший). Тип интеграции: Python-сервис (`integrations/qtickets/loader.py`).
- **QTickets Google Sheets** — основной источник заказов и инвентаря. Тип интеграции: Python-сервис (`integrations/qtickets_sheets/loader.py`).
- **VK Ads API** — источник маркетинговых метрик. Тип интеграции: Python-сервис (`integrations/vk_ads/loader.py`).
- **Яндекс.Директ API** — источник маркетинговых метрик. Тип интеграции: Python-сервис (`integrations/direct/loader.py`).
- **Gmail API** — резервный канал для данных QTickets. Тип интеграции: Python-сервис (`integrations/gmail/loader.py`).
- **ClickHouse** — основное хранилище данных (single-node), содержит таблицы `stg_*` (стейджинг), `fact_*` (факты), `dim_*` (справочники) и `v_*` (витрины). Развертывается через Docker Compose (`infra/clickhouse/`).
- **Yandex DataLens** — целевая BI-платформа, визуализирует показатели из ClickHouse через HTTPS.

## 2. Поток A1 — QTickets Google Sheets → ClickHouse
1. Python-лоадер (`integrations/qtickets_sheets/loader.py`) выполняется каждые 15 минут.
2. Процесс:
   - Загружает конфигурацию из `.env.qtickets_sheets` (`GSERVICE_JSON`, `SHEET_ID_*`, `CH_*`).
   - Читает данные из Google Sheets (Events, Inventory, Sales).
   - Нормализует данные: даты в MSK, города в lowercase, числа с точкой.
   - Вставляет в `zakaz.stg_qtickets_sheets_*` и `zakaz.dim_events` с `ReplacingMergeTree(_ver)`.
   - Записывает метаданные о запуске в `zakaz.meta_job_runs`.
3. Идемпотентность обеспечивается через `_ver` и `ReplacingMergeTree`.

## 3. Поток A2 — QTickets API → ClickHouse (устаревший)
1. Python-лоадер (`integrations/qtickets/loader.py`) выполняется каждые 15 минут.
2. Процесс:
   - Загружает конфигурацию из `.env.qtickets` (`QTICKETS_*`, `CH_*`).
   - Запрашивает мероприятия, инвентарь и продажи из QTickets API.
   - Нормализует данные: даты в MSK, города в lowercase, числа с точкой.
   - Вставляет в `zakaz.stg_qtickets_sales_raw` и `zakaz.dim_events` с `ReplacingMergeTree(_ver)`.
   - Записывает метаданные о запуске в `zakaz.meta_job_runs`.
3. Идемпотентность обеспечивается через `_ver` и `ReplacingMergeTree`.

## 4. Поток B1 — VK Ads API → ClickHouse
1. Python-лоадер (`integrations/vk_ads/loader.py`) выполняется ежедневно в 00:00 MSK.
2. Процесс:
   - Загружает конфигурацию из `.env.vk` (`VK_*`, `CH_*`).
   - Получает список кампаний и объявлений.
   - Забирает статистику пачками по 200 объявлений за предыдущий день.
   - Парсит UTM-метки из `link_url`, включая `utm_content` формата `<city>_<dd>_<mm>`.
   - Вставляет данные в `zakaz.fact_vk_ads_daily` с `ReplacingMergeTree(_ver)`.
   - Записывает метаданные о запуске в `zakaz.meta_job_runs`.
3. Логи и метрики доступны через systemd journal и таблицу `zakaz.meta_job_runs`.

## 5. Поток C1 — Яндекс.Директ API → ClickHouse
1. Python-лоадер (`integrations/direct/loader.py`) выполняется ежедневно в 00:10 MSK.
2. Процесс:
   - Загружает конфигурацию из `.env.direct` (`DIRECT_*`, `CH_*`).
   - Формирует отчет с детализацией по объявлениям за предыдущий день.
   - Парсит UTM-метки из отчета, включая `utm_content` формат `<city>_<dd>_<mm>`.
   - Вставляет данные в `zakaz.fact_direct_daily` с `ReplacingMergeTree(_ver)`.
   - Записывает метаданные о запуске в `zakaz.meta_job_runs`.

## 6. Поток D1 — Gmail API → ClickHouse (резервный канал)
1. Python-лоадер (`integrations/gmail/loader.py`) выполняется каждые 4 часа (отключен по умолчанию).
2. Процесс:
   - Аутентификация через OAuth2 с учетными данными в `secrets/gmail/`.
   - Поиск писем по запросу (QTickets, продажи и т.д.).
   - Извлечение данных из HTML таблиц и CSV вложений.
   - Нормализация и вставка в `zakaz.stg_qtickets_sales_raw` с `src_msg_id` для трассировки.
   - Записывает метаданные о запуске в `zakaz.meta_job_runs`.
3. Используется только при недоступности основного QTickets API.

## 7. Поток E1 — Витрины в ClickHouse
1. Представления создаются через DDL (`infra/clickhouse/init_integrations.sql`):
   - `zakaz.v_sales_latest` — актуальные данные о продажах без дублей
   - `zakaz.v_sales_14d` — продажи за последние 14 дней
   - `zakaz.v_marketing_daily` — сводная статистика по маркетингу
   - `zakaz.v_romi_kpi` — ROMI KPI с цветовой индикацией
   - `zakaz.v_campaign_performance` — эффективность рекламных кампаний
2. Автоматически обновляются при поступлении новых данных в таблицы-источники.

## 8. Поток F0 — ClickHouse → DataLens
1. HTTPS-доступ к ClickHouse обеспечивается через реверс-прокси Caddy.
2. DataLens подключается к ClickHouse через пользователя `datalens_reader` (только чтение).
3. BI-слой организован через представления:
   - `v_sales_latest` — актуальные данные о продажах без дубликатов
   - `v_sales_14d` — агрегированные данные за 14 дней для быстрых графиков
   - `v_marketing_daily` — сводная статистика по маркетингу
   - `v_romi_kpi` — ROMI KPI с цветовой индикацией (>1.5/1-1.5/<1)
   - `v_campaign_performance` — эффективность рекламных кампаний
   - `v_data_freshness` — свежесть данных по источникам
4. В DataLens создаются:
   - Подключение `ch_zakaz_prod` к ClickHouse через HTTPS
   - Источник `src_ch_sales_latest` на основе SQL-запроса к `v_sales_latest`
   - Источник `src_ch_marketing_daily` на основе `v_marketing_daily`
   - Датасет `ds_sales` с измерениями и метриками
   - Датасет `ds_marketing` с рекламными метриками
   - Дашборд `Zakaz: Продажи и Реклама` с виджетами продаж, затрат и ROMI
5. Контроль качества данных выполняется через `infra/clickhouse/datalens_checks.sql` и `infra/clickhouse/smoke_checks_integrations.sql`.

## 9. Управление схемами и качеством данных
- `infra/clickhouse/init.sql` — DDL для создания базовых таблиц ClickHouse.
- `infra/clickhouse/init_integrations.sql` — DDL для таблиц интеграций и витрин.
- `infra/clickhouse/init_qtickets_sheets.sql` — DDL для таблиц QTickets Google Sheets.
- `infra/clickhouse/smoke_checks.sql` — базовые SQL-проверки качества данных.
- `infra/clickhouse/smoke_checks_integrations.sql` — проверки качества данных интеграций.
- `infra/clickhouse/smoke_checks_qtickets_sheets.sql` — проверки качества данных QTickets Sheets.
- `integrations/common/` — общие утилиты для всех загрузчиков (CH, время, UTM, логирование).
- Миграции схем выполняются через PR в репозиторий → применение DDL → обновление DataLens.

## 10. Планировщик и мониторинг
- **Systemd таймеры** (`ops/systemd/`) управляют запуском загрузчиков:
  - `qtickets_sheets.timer` — каждые 15 минут (основной источник)
  - `qtickets.timer` — каждые 15 минут (устаревший, может быть отключен)
  - `vk_ads.timer` — ежедневно в 00:00 MSK
  - `direct.timer` — ежедневно в 00:10 MSK
  - `gmail_ingest.timer` — каждые 4 часа (отключен)
  - `alerts.timer` — каждые 2 часа
- **Healthcheck сервер** (`ops/healthcheck_integrations.py`) предоставляет HTTP эндпоинты:
  - `/healthz` — базовая проверка
  - `/healthz/detailed` — детальная проверка с метриками
  - `/healthz/freshness` — проверка свежести данных
  - `/healthz/qtickets_sheets` — проверка состояния QTickets Sheets интеграции
- **Система алертов** (`ops/alerts/notify.py`) отправляет email уведомления о проблемах.
- Метаданные о запусках сохраняются в `zakaz.meta_job_runs` и `zakaz.alerts`.

## 10. Безопасность и доступы
- Все секреты хранятся в `secrets/` (в .gitignore) с правами 600.
- Переменные окружения загружаются из `.env.*` файлов.
- Сетевой доступ к ClickHouse ограничен: только через HTTPS-прокси Caddy.
- Ролевая модель доступа: `etl_writer` (запись), `datalens_reader` (чтение), `backup_user` (бэкапы).
- Аудит и логирование всех запросов включены с ретеншеном 30 дней.
- Оповещения об ошибках отправляются на `ads-irsshow@yandex.ru`.

## 11. Текущее состояние и план эволюции

### Реализовано (v1.1.0) — EPIC-INT-ALL + TASK-QT-SHEETS-ONLY
- Полноценная сквозная интеграция: Gmail/QTickets/VK/Direct → ClickHouse → DataLens
- **QTickets Google Sheets интеграция** как основной источник данных (замена нестабильного API)
- Единый модуль `integrations/common/` с утилитами для всех загрузчиков
- Нормализация UTM-меток формата `<city>_<dd>_<mm>` с автоматическим парсингом
- Системные таймеры для всех загрузчиков с оптимальным расписанием
- Healthcheck сервер с HTTP эндпоинтами для внешнего мониторинга
- Система алертов с email уведомлениями и сохранением в БД
- Smoke-проверки для контроля качества данных
- Дашборд DataLens с ROMI-светофором и аналитикой по городам
- Резервный канал Gmail на случай недоступности QTickets Sheets
- Идемпотентная загрузка с дедупликацией на основе хэшей

### Следующие шаги
- Создание материализованных представлений в ClickHouse для производительности
- Добавление прогнозирования продаж на основе исторических данных
- Интеграция с системами аналитики (Google Analytics, Яндекс.Метрика)
- Расширение UTM-аналитики с воронкой продаж
- Автоматическое обнаружение аномалий в данных
- API для внешних систем получения метрик
- Деактивация старого QTickets API после полного перехода на Google Sheets
