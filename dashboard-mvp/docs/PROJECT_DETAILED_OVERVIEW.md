# Zakaz Dashboard — подробное инженерное описание

Документ предназначен для разработчиков и аналитиков, которым нужно быстро ввести новый ИИ‑или человеческий агент в курс проекта. Описывает бизнес‑контекст, архитектуру, кодовую базу, инфраструктуру, операционные процессы и тестовый контур.

---

## 1. Назначение проекта и бизнес‑контекст

| Параметр | Значение |
| --- | --- |
| **Основная задача** | Собрать управляемый дашборд продаж и маркетинга Zakaz в Yandex DataLens, автоматизировать загрузку QTickets, VK Ads и резервных источников. |
| **Горизонт** | MVP A0–A2 (Sheets + DataLens), расширение B0–B3 (полный автопоток VK Ads), C0 (миграция на ClickHouse). |
| **Ограничения** | 10–14 календарных дней, бюджет 45 000 ₽, только бесплатные коннекторы и сервис‑аккаунты. |
| **Ключевые KPI** | SLA данных ≤ 2 ч после полуночи MSK, 3 страницы дашборда (Продажи, Инвентарь, Маркетинг), 100 % покрытие документацией (docs/). |

Команда и роли перечислены в `docs/PROJECT_OVERVIEW.md`. Приёмка фиксируется в `EPIC-CH-0*.md`, `TASK-*.md`, `docs/FINAL_*`.

---

## 2. Сквозная архитектура

```
┌────────────┐   Apps Script   ┌───────────────┐
│ QTickets   │  (архив/Sheets) │ Google Sheets │
└─────┬──────┘                 └─────┬────────┘
      │ Python (integrations/qtickets_sheets, ch-python)
      ▼
┌───────────────────────────────────────────────┐
│                 ClickHouse                    │
│ stg_* / dim_* / fact_* / v_* / meta_job_runs  │
└─────┬────────────┬─────────────┬──────────────┘
      │            │             │
      │            │             │
      │            │             │
      ▼            ▼             ▼
┌────────────┐ ┌────────────┐ ┌──────────────┐
│ VK Ads API │ │ Direct API │ │ Gmail (raw) │
└────────────┘ └────────────┘ └──────────────┘
      │            │             │
      ▼            ▼             ▼
 integr. modules  integr. modules  mail-python
      │            │             │
      └────────────┴───────┬─────┘
                            ▼
                        DataLens
```

### Потоки данных

| ID | Источник → назначение | Компонент | Расписание | Таблицы ClickHouse | Примечания |
| --- | --- | --- | --- | --- | --- |
| A1 | Google Sheets (QTickets, Inventory, Sales) → ClickHouse | `integrations/qtickets_sheets` + `ch-python/loader/...` | каждые 30 мин (`qtickets_sheets.timer`) | `stg_qtickets_sheets_*`, `dim_events`, `fact_qtickets_*` | Основной канал после отказа от API. |
| A2 (legacy) | QTickets API → Google Sheets | `archive/appscript/qtickets_api_ingest.gs` | дневной триггер Apps Script | Листы `QTickets`, `Inventory`, `Logs` | Используется только при аварийном возврате к Sheets. |
| B1 | VK Ads API → ClickHouse | `integrations/vk_ads` или `vk-python` | ежедневно 00:00 MSK (`vk_ads.timer`) | `stg_vk_ads_daily`, `fact_vk_ads_daily` | Поддержка UTM, дедуп по ключу `date+campaign+adgroup`. |
| C1 | Яндекс.Директ API → ClickHouse | `integrations/direct` | ежедневно 00:10 MSK (`direct.timer`) | `fact_direct_daily` | Собирает статистику по объявлениям, парсит UTM. |
| D1 | Gmail → ClickHouse | `mail-python/gmail_ingest.py` | каждые 4 ч (`gmail_ingest.timer`, выключен по умолчанию) | `stg_mail_sales_raw`, `v_sales_latest/14d` | Резервный канал на случай падения QTickets. |
| BI | ClickHouse → DataLens | `bi/`, `docs/DATALENS_*` | автообновление 15 мин | `v_sales_daily`, `v_vk_ads_daily`, `v_marketing_roi_daily`, `v_ops_freshness` | Дашборды: Sales Overview, Marketing ROI, City Performance, Ops & Quality. |

---

## 3. Структура репозитория

| Каталог/файл | Содержание |
| --- | --- |
| `docs/` | Полный пакет документации: архитектура, runbook’и, risk log, communication plan, ADR (`docs/adr/*`), тестовые сценарии (`docs/E2E_*`, `docs/REAL_DATA_*`). |
| `integrations/` | Производственные загрузчики (qtickets, qtickets_sheets, vk_ads, direct, gmail) и утилиты `common/` (ClickHouse клиент, UTM parser, time/logging helpers). |
| `vk-python/` | Изолированный пакет `vk-ads-pipeline` (pyproject, src/, tests/) для ClickHouse sink + CSV выгрузки. |
| `ch-python/` | CLI (`cli.py`) и билдеры витрин/CDC (`loader/*.py`) для ClickHouse. |
| `mail-python/` | Gmail ingest + ClickHouse init скрипты, `.env.sample`, secrets/guide. |
| `infra/clickhouse/` | Docker Compose, Caddyfile, users, DDL (`init*.sql`), smoke SQL (`smoke_checks*.sql`). |
| `infra/systemd/` | Примеры сервисов/таймеров для развёртываний на VPS (cdc, etl, backup). |
| `ops/` | Чек-листы, deploy/backup скрипты, healthcheck/alerts, quality SLI, systemd helper `manage_timers.sh`. |
| `bi/` | Описания датасетов и дашбордов для DataLens, экспортированные JSON. |
| `archive/` | Декомиссионные артефакты Google Sheets (Apps Script, YAML схемы, init/validate утилиты). |
| Корневые файлы | README, CHANGELOG, отчёты по эпикам/таскам, shell скрипты тестов (`e2e_test_*.sh`, `test_system.sh`). |

---

## 4. Потоки и компоненты (детально)

### 4.1 QTickets Google Sheets → ClickHouse (A1)
- **Файлы**: `integrations/qtickets_sheets/loader.py`, `gsheets_client.py`, `transform.py`, `upsert.py`.
- **Конфигурация**: `secrets/.env.qtickets_sheets` (ID таблиц, листов, ключи дедуп, TZ).
- **Алгоритм**:
  1. `GoogleSheetsClient` получает листы Sales / Events / Inventory сервисным аккаунтом.
  2. `DataTransformer` нормализует даты (MSK), города (lowercase), числовые поля, проверяет обязательные колоноки.
  3. `ClickHouseUpsert` записывает в `stg_qtickets_sheets_raw` + профильные таблицы, обновляет `dim_events`.
  4. Метаданные запуска попадают в `zakaz.meta_job_runs`.
- **Расписание**: systemd `qtickets_sheets.timer` (каждые 15 мин). См. `ops/systemd/README.md`.
- **Качество**: smoke SQL `infra/clickhouse/smoke_checks_qtickets_sheets.sql`; Python тест `test_qtickets_sheets.py`.

### 4.2 QTickets API → Google Sheets (A2, архив)
- **Файлы**: `archive/appscript/qtickets_api_ingest.gs`.
- **Назначение**: резервный канал, когда данных в Sheets нет (Apps Script создаёт листы `QTickets`, `Inventory`, `Logs`, логирует и отправляет email).
- **Инициализация**: по инструкции `archive/appscript/README.md` + YAML схемы `archive/sheets/*.yaml` + утилиты `archive/sheets_init.py`, `sheets_validate.py`.

### 4.3 VK Ads (B0–B3)
**A. Интеграция `integrations/vk_ads/loader.py`**
- Конфиг из `secrets/.env.vk` (`VK_TOKEN`, `VK_ACCOUNT_IDS`, `VK_DAYS_BACK`, `CH_*`).
- Получает кампании/объявления, парсит UTM, загружает в `fact_vk_ads_daily`.
- Таймер `vk_ads.timer` + логирование в `logs/vk_ads.log` (опционально через env).

**B. Сервис `vk-python/`**
- `config.py`: строгая валидация окружения (обязательные токены, даты, метрики), поддержка dry-run и CSV.
- `client.py`: HTTPX клиент, ошибки типизированы (`VkAdsError`).
- `pipeline.py`: orchestrator, chunks по 200 ID, возможность ClickHouse sink или CSV.
- `sink/clickhouse_sink.py`: преобразует `cost`→копейки, генерирует md5 `_dedup_key`, вставляет в `stg_vk_ads_daily`.
- `transform/normalize.py` и `transforms.py`: парсинг UTM/городов, нормализация дат/метрик.
- Тесты: `tests/test_config.py`, `tests/test_transforms.py`.

### 4.4 Яндекс.Директ
- **Файл**: `integrations/direct/loader.py`.
- **Особенности**: формирует отчет с детализацией по объявлениям, обогащает `utm_city`/`utm_day`/`utm_month`, дедуп на уровне ClickHouse (`ReplacingMergeTree`). Метаданные — `meta_job_runs`.

### 4.5 Gmail резерв
- **Файлы**: `mail-python/gmail_ingest.py`, `.env.sample`, `init_clickhouse.sh`, `README.md`.
- **Алгоритм**:
  1. Авторизация по OAuth (`secrets/gmail/credentials.json` → `token.json`).
  2. Парсинг CSV/HTML таблиц (`pandas + BeautifulSoup`), нормализация чисел/дат/валют.
  3. Расчёт `row_hash`, запись в `zakaz.stg_mail_sales_raw`.
- **Автоматизация**: systemd `gmail-ingest.service/timer` (копируется из `infra/systemd/` или `ops/systemd/` в /etc/systemd/system).
- **Документация**: `README_MAIL_DASHBOARD.md`, `docs/DATALENS_MAIL_SETUP.md`.

### 4.6 Общие утилиты
- `integrations/common/ch.py`: ClickHouse клиент с retry, TLS, `insert/execute/command`.
- `integrations/common/utm.py`: парсит `utm_content` формата `<city>_<dd>_<mm>`, нормализует города.
- `integrations/common/logging.py`, `time.py`: унификация логов и работы с таймзонами.

### 4.7 CLI и витрины (`ch-python/`)
- `cli.py` предоставляет команды:
  - `load-sheets` (Sheets → CH),
  - `cdc-qtickets` / `cdc-vk` (инкрементальные CDC),
  - `build-dm-sales`, `build-dm-vk`, `build-dm-sales-incr`, `build-dm-vk-incr` (витрины + SLI).
- `loader/*.py` содержит реализацию построителей и CDC пайплайнов.
- Использует `.env` (ClickHouse + Google). Default batch size 1000, логирование через `logging`.

---

## 5. Инфраструктура

### 5.1 ClickHouse (Docker Compose)
- **Расположение**: `infra/clickhouse/`.
- **Развёртывание**: `docker compose up -d`, затем `init.sql` / `init_integrations.sql` / `init_mail.sql`.
- **HTTP/HTTPS**: Caddy (`Caddyfile`) выдаёт HTTPS для DataLens; пароли настраиваются в корневом `.env`.
- **Пользователи**: `admin`, `etl_writer`, `datalens_reader` (описаны в `README.md` + `users.d/`).
- **Таблицы**:
  - `stg_qtickets_*`, `stg_vk_ads_daily`, `fact_vk_ads_daily`, `fact_qtickets_*`, `fact_direct_daily`.
  - `dim_events`, `meta_job_runs`, `meta_etl_runs`.
  - Витрины `v_sales_latest`, `v_sales_14d`, `v_vk_ads_daily`, `v_marketing_roi_daily`, `v_ops_freshness`.
- **Дедупликация**: `ReplacingMergeTree(_ver)` + `_dedup_key`.
- **Smoke / e2e**: SQL файлы `smoke_checks*.sql`, `datalens_checks.sql`; shell `test_clickhouse_setup.py`, `e2e_test_simple.sh`, `test_system.sh`.

### 5.2 Systemd и автоматизация
- **Два набора**:
  - `infra/systemd/`: унифицированные `etl@.service`, `backup@*.timer`, `gmail-ingest.*`.
  - `ops/systemd/`: конечные сервисы (`qtickets.service/timer`, `vk_ads.*`, `direct.*`, `alerts.*`, `healthcheck.*`) + `manage_timers.sh`.
- Все сервисы запускаются от пользователя `etl`, используют `PYTHONPATH=/opt/zakaz_dashboard`, перезапускаются `Restart=on-failure`.

### 5.3 Мониторинг и алерты
- **Healthcheck**: `ops/healthcheck.py` (CLI) и `ops/healthcheck_integrations.py` (HTTP сервер `/healthz`, `/healthz/detailed`, `/healthz/freshness`).
- **Alerts**: `ops/alerts/notify.py` (email через SMTP, конфиг `secrets/.env.alerts`). Таймер `alerts.timer` проверяет ошибки запусков и свежесть каждые 2 часа.
- **Quality/SLO**: `ops/quality_sli.py`, `ops/slo_guard.py`, `ops/quality_sli.py`. Данные для SLI лежат в `meta` таблицах.
- **Бэкапы**: `ops/backup_full.sh`, `backup_incr.sh`, `backup_prune.sh`, `backup_verify.py`, `restore_test.sh`; таймеры в `infra/systemd/`.

---

## 6. BI‑слой и DataLens

- **Каталог `bi/`** содержит:
  - `datasets/` — YAML/MD описания полей, вычисляемых метрик (`ds_sales_daily`, `ds_vk_ads_daily`, `ds_roi_daily`).
  - `dashboards/` — описания страниц (Sales Overview, Marketing ROI, City Performance, Ops & Data Quality).
  - `exports/` — выгрузки DataLens объектов (ID для восстановления).
- **Документация**: `docs/DATALENS_CONNECTION_PLAN.md`, `docs/DATALENS_TECHNICAL_SPEC.md`, `docs/DATALENS_IMPLEMENTATION_SUMMARY.md`, `docs/RUNBOOK_DATALENS.md`.
- **Настройки**: кэш 10–15 мин, автообновление каждые 15 мин, ограничение `max_execution_time=30s`, роли `bi_viewers`/`bi_admins`.

---

## 7. Тестирование и контроль качества

| Слой | Инструменты | Файлы |
| --- | --- | --- |
| Unit/functional | `pytest` | `vk-python/tests/*`, `test_qtickets_sheets.py`, `test_google_sheets.py`. |
| Инфраструктура | shell/python | `test_clickhouse_setup.py`, `e2e_test_simple.sh`, `e2e_test_real_data.sh`, `test_system.sh`. |
| SQL smoke | ClickHouse | `infra/clickhouse/smoke_checks.sql`, `smoke_checks_integrations.sql`, `smoke_checks_qtickets_sheets.sql`. |
| Документы | Runbook’и | `docs/E2E_TESTING_SCRIPT.md`, `docs/E2E_TESTING_RESULTS_REPORT.md`, `docs/REAL_DATA_*`. |
| Pre-commit | `tools/init.sh` → `.pre-commit-config.yaml` (black, markdownlint, базовые хуки). |

---

## 8. Конфигурации и секреты

- **Корневой `.env`** (копия из `.env.sample`) содержит `CLICKHOUSE_*`, `VK_*` по умолчанию.
- **Секреты**: каталог `secrets/` не в git. Для каждого модуля копируем `.env.<source>.sample` из `configs/` (например `.env.vk`, `.env.direct`, `.env.qtickets_sheets`, `.env.alerts`) → `secrets/.env.<source>` и заполняем.
- **Google**: сервисный json (`secrets/google/sa.json`) + Gmail OAuth (`mail-python/secrets/gmail/credentials.json` → `token.json`).
- **VK Ads pipeline**: переменные описаны в `vk-python/README.md` (`VK_ACCESS_TOKEN`, `VK_ACCOUNT_ID`, `VK_IDS_TYPE`, `SPREADSHEET_ID`, `GOOGLE_SA_JSON_PATH`, `CLICKHOUSE_*`, `VK_SINK`). Сервис может писать в Google Sheets (устаревший вариант) или ClickHouse.
- **Alerts**: SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO`) в `secrets/.env.alerts`.

Секреты передаются таймерам через `EnvironmentFile=` или экспортируются перед запуском CLI.

---

## 9. Процедура онбординга инженера

1. **Прочитать документацию**: `README.md`, `docs/PROJECT_OVERVIEW.md`, `docs/ARCHITECTURE.md`, нужные runbook’и.
2. **Инициализировать окружение**: `python -m venv .venv && source .venv/bin/activate`, `bash tools/init.sh`, `pip install -r requirements.txt` при необходимости (каждый модуль отдельно).
3. **Настроить .env/secrets**: скопировать `.env.sample` → `.env`, создать `secrets/.env.*`, добавить Google creds.
4. **Развернуть ClickHouse локально**: `cd infra/clickhouse && docker compose up -d`, затем `docker exec -i ch-zakaz clickhouse-client --user=admin --password=$CLICKHOUSE_ADMIN_PASSWORD < init.sql`.
5. **Проверить smoke**: `docker exec ch-zakaz clickhouse-client -q "SHOW TABLES FROM zakaz"`, `clickhouse-client < smoke_checks.sql`.
6. **Прогнать пайплайны**:
   - `python -m integrations.qtickets_sheets.loader --envfile secrets/.env.qtickets_sheets --ch-env secrets/.env.ch --dry-run`.
   - `cd vk-python && python -m vk_ads_pipeline.main --dry-run --sink clickhouse`.
   - `python mail-python/gmail_ingest.py --dry-run --limit 5`.
7. **Настроить автоматизацию**: `ops/systemd/manage_timers.sh install`, затем `enable/start` нужные таймеры (qtickets_sheets, vk_ads, direct, alerts). Проверить `journalctl -u <service>`.
8. **Подключить DataLens**: следовать `docs/DATALENS_CONNECTION_PLAN.md`, восстановить датасеты/дашборды из `bi/`.
9. **Настроить мониторинг**: развернуть `healthcheck.service`, заполнить `secrets/.env.alerts`, включить `alerts.timer`. Проверить `/healthz` и `meta_job_runs`.
10. **Задокументировать изменения**: обновить соответствующие отчетные файлы (`FINAL_STATUS_REPORT.md`, `TASK-*.md`) при завершении задач.

---

## 10. Известные риски и дальнейшие шаги

Список поддерживается в `docs/RISK_LOG.md`. Основные категории:
1. **Доступы и токены** — задержка выдачи сервисных аккаунтов Google / VK / Direct, истечение токенов Gmail/SMTP (см. `ops/TOKEN_GUIDE.md`).
2. **Изменения форматов** — QTickets и маркетинговые отчёты могут менять колонки; для этого предусмотрены YAML схемы (archive) и либы парсинга.
3. **Производительность ClickHouse** — сейчас single-node; нужны materialized views и ретенции (см. `docs/ARCHITECTURE.md` → «Следующие шаги»).
4. **Мониторинг** — при выключенных таймерах alerts нет уведомлений; healthcheck нужно держать включённым.
5. **Дубли каналов** — переход с Sheets на CDC должен сопровождаться отключением устаревших скриптов, иначе возможны расхождения.

Рекомендованные улучшения (из `docs/ARCHITECTURE.md` и финальных отчётов):
- Дополнить ClickHouse материализованными представлениями для ускорения DataLens.
- Добавить автоматическое обнаружение аномалий и расширенную UTM‑аналитику.
- Завершить миграцию с Google Sheets, удалить архивные компоненты после финального cut‑over.
- Расширить резервный канал (Gmail/Direct API) и автоматические smoke‑проверки.

---

## 11. Быстрые ссылки

| Тема | Файл |
| --- | --- |
| High-level overview | `README.md`, `docs/PROJECT_OVERVIEW.md` |
| Архитектура | `docs/ARCHITECTURE.md`, `docs/adr/ADR-0001-clickhouse-base.md`, `docs/adr/ADR-0002-datalens-connection.md` |
| Потоки интеграций | `integrations/*/README.md`, `vk-python/README.md`, `mail-python/README.md` |
| Хранилище | `infra/clickhouse/README.md`, `init*.sql`, `smoke_checks*.sql` |
| Systemd / Ops | `ops/systemd/README.md`, `ops/alerts/README.md`, `ops/README_BACKUP.md` |
| DataLens | `bi/README.md`, `docs/DATALENS_*`, `docs/RUNBOOK_DATALENS.md` |
| Тесты | `docs/E2E_TESTING_SCRIPT.md`, `docs/E2E_TESTING_RESULTS_REPORT.md`, `docs/REAL_DATA_*`, `test_*.py`, `e2e_test_*.sh` |
| Приёмка и отчётность | `docs/DOR_CHECKLIST_A0.md`, `docs/DOD_CHECKLIST_A0.md`, `docs/FINAL_*`, `EPIC-CH-*.md`, `TASK-*.md` |

---

Этот документ можно передавать любому новому разработчику или ИИ‑агенту как центральную справку. Для глубокой работы переходите к связанным README/runbook’ам из таблицы «Быстрые ссылки».
