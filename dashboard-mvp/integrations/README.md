# Интеграции Zakaz Dashboard

## Обзор

Система интеграций Zakaz Dashboard обеспечивает автоматическую загрузку данных из различных источников в ClickHouse для анализа в DataLens.

## Архитектура

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   QTickets   │    │   VK Ads    │    │ Яндекс.Директ│    │    Gmail    │
│     API       │    │     API      │    │     API      │    │     API     │
└─────┬───────┘    └─────┬───────┘    └─────┬───────┘    └─────┬───────┘
      │                    │                    │                    │
      ▼                    ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ClickHouse (Single Node)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ stg_qtickets│  │fact_vk_ads │  │fact_direct │  │stg_qtickets│     │
│  │   _sales_raw│  │   _daily    │  │   _daily    │  │   _sales_raw│     │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ dim_events  │  │fact_vk_ads │  │fact_direct │  │dim_events  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │v_sales_latest│  │v_marketing_ │  │v_campaign_  │  │v_sales_latest│     │
│  │              │  │   daily     │  │performance│  │              │     │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
      │                    │                    │                    │
      ▼                    ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DataLens                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Продажи    │  │  ROMI       │  │  Воронка     │  │  Города      │     │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Компоненты

### Источники данных

| Источник | Описание | Частота обновления | Статус |
|----------|----------|-------------------|--------|
| QTickets API | Продажи билетов и мероприятия | Каждые 15 минут | 🟢 Основной |
| VK Ads API | Статистика рекламных кампаний | Ежедневно в 00:00 MSK | 🟢 Основной |
| Яндекс.Директ API | Статистика рекламных кампаний | Ежедневно в 00:10 MSK | 🟢 Основной |
| Gmail API | Резервный канал для QTickets | Каждые 4 часа (отключен) | 🟡 Резервный |

### Общие утилиты

- **`integrations/common/ch.py`** - клиент ClickHouse с retry и TLS
- **`integrations/common/time.py`** - работа с таймзоной MSK
- **`integrations/common/utm.py`** - парсинг UTM-меток формата `<city>_<dd>_<mm>`
- **`integrations/common/logging.py`** - структурированное логирование с метриками

### Загрузчики

- **`integrations/qtickets/`** - загрузчик QTickets API
- **`integrations/vk_ads/`** - загрузчик VK Ads API
- **`integrations/direct/`** - загрузчик Яндекс.Директ API
- **`integrations/gmail/`** - резервный канал Gmail API

### Планировщик и мониторинг

- **`ops/systemd/`** - systemd таймеры для автоматического запуска
- **`ops/alerts/`** - система алертов с email уведомлениями
- **`ops/healthcheck_integrations.py`** - HTTP healthcheck сервер

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install clickhouse-connect python-dotenv requests httpx beautifulsoup4 pandas
```

### 2. Настройка ClickHouse

```bash
# Применение DDL
clickhouse-client --host localhost --port 8123 -u default \
  --query "$(cat infra/clickhouse/init_integrations.sql)"
```

### 3. Настройка источников данных

Скопируйте шаблоны конфигурации и заполните реальные значения:

```bash
# QTickets
cp configs/.env.qtickets.sample secrets/.env.qtickets

# VK Ads
cp configs/.env.vk.sample secrets/.env.vk

# Яндекс.Директ
cp configs/.env.direct.sample secrets/.env.direct

# Gmail
cp configs/.env.gmail.sample secrets/.env.gmail

# ClickHouse
cp configs/.env.ch.sample secrets/.env.ch

# Алерты
cp configs/.env.alerts.sample secrets/.env.alerts
```

### 4. Запуск загрузчиков

```bash
# QTickets
python3 integrations/qtickets/loader.py

# VK Ads
python3 integrations/vk_ads/loader.py

# Яндекс.Директ
python3 integrations/direct/loader.py

# Gmail (резервный канал)
python3 integrations/gmail/loader.py
```

### 5. Настройка автоматического запуска

```bash
# Установка таймеров
cd ops/systemd
sudo ./manage_timers.sh install

# Включение таймеров
sudo ./manage_timers.sh enable qtickets
sudo ./manage_timers.sh enable vk_ads
sudo ./manage_timers.sh enable direct
sudo ./manage_timers.sh enable alerts

# Включение healthcheck сервера
sudo systemctl enable healthcheck.service
sudo systemctl start healthcheck.service
```

## Мониторинг

### Healthcheck эндпоинты

```bash
# Базовая проверка
curl http://localhost:8080/healthz

# Детальная проверка
curl http://localhost:8080/healthz/detailed

# Проверка свежести данных
curl http://localhost:8080/healthz/freshness
```

### Smoke-тестирование

```bash
# Запуск smoke-тестов
python3 ops/smoke_test_integrations.py

# С сохранением результатов
python3 ops/smoke_test_integrations.py --output smoke_test_results.json

# Через обертку
./ops/run_smoke_test.sh run-with-results
```

### Алерты

```bash
# Проверка ошибок
python3 ops/alerts/notify.py --check-errors

# Проверка свежести данных
python3 ops/alerts/notify.py --check-freshness

# Полная проверка
python3 ops/alerts/notify.py --check-health
```

## Структура каталогов

```
integrations/
├── common/                 # Общие утилиты
│   ├── ch.py              # ClickHouse клиент
│   ├── time.py            # Работа с временем
│   ├── utm.py             # Парсинг UTM-меток
│   ├── logging.py         # Логирование
│   └── __init__.py
├── qtickets/               # QTickets интеграция
│   ├── loader.py          # Загрузчик
│   ├── README.md          # Документация
│   └── __init__.py
├── vk_ads/                 # VK Ads интеграция
│   ├── loader.py          # Загрузчик
│   ├── README.md          # Документация
│   └── __init__.py
├── direct/                 # Яндекс.Директ интеграция
│   ├── loader.py          # Загрузчик
│   ├── README.md          # Документация
│   └── __init__.py
├── gmail/                  # Gmail интеграция
│   ├── loader.py          # Загрузчик
│   ├── README.md          # Документация
│   └── __init__.py
└── __init__.py
```

## Расписание загрузчиков

### QTickets API

**Назначение**: Загрузка данных о продажах билетов и мероприятиях.

**Особенности**:
- Загрузка мероприятий, инвентаря и продаж
- Нормализация городов в lowercase
- Поддержка различных форматов дат
- Идемпотентность через `ReplacingMergeTree`

**Расписание**: [integrations/qtickets/README.md](qtickets/README.md)

### VK Ads API

**Назначение**: Загрузка статистики рекламных кампаний VK Ads.

**Особенности**:
- Детализация по группам объявлений
- Парсинг UTM-меток из URL объявлений
- Автоматическое извлечение города из `utm_content`
- Чанковая загрузка по 200 ID

**Расписание**: [integrations/vk_ads/README.md](vk_ads/README.md)

### Яндекс.Директ API

**Назначение**: Загрузка статистики рекламных кампаний Яндекс.Директ.

**Особенности**:
- Получение отчетов через API
- Поддержка различных форматов чисел
- Автоматическое извлечение города из `utm_content`
- TSV формат отчетов

**Расписание**: [integrations/direct/README.md](direct/README.md)

### Gmail API

**Назначение**: Резервный канал для данных QTickets.

**Особенности**:
- Извлечение данных из HTML таблиц и CSV вложений
- Поддержка различных кодировок (UTF-8, CP1251)
- Гибкая обработка форматов данных
- OAuth2 аутентификация

**Расписание**: [integrations/gmail/README.md](gmail/README.md)

## UTM-аналитика

### Формат utm_content

Система автоматически парсит UTM-метки формата `<city>_<dd>_<mm>`:

- `utm_city` - город в нижнем регистре
- `utm_day` - день месяца
- `utm_month` - месяц

### Примеры

| utm_content | utm_city | utm_day | utm_month |
|------------|-----------|----------|------------|
| msk_01_10 | москва | 1 | 10 |
| spb_15_09 | санкт-петербург | 15 | 9 |
| nnv_20_08 | нижний новгород | 20 | 8 |

### Нормализация городов

Система нормирует названия городов:

```python
"MSK" → "москва"
"СПБ" → "санкт-петербург"
"NNV" → "нижний новгород"
```

## Расписание systemd таймеров

| Таймер | Расписание | Расписание | Статус |
|--------|------------|------------|--------|
| qtickets.timer | Каждые 15 минут | Загрузка данных QTickets API | Включен |
| vk_ads.timer | Ежедневно 00:00 MSK | Загрузка статистики VK Ads | Включен |
| direct.timer | Ежедневно 00:10 MSK | Загрузка статистики Яндекс.Директ | Включен |
| gmail_ingest.timer | Каждые 4 часа | Резервный канал Gmail | Отключен |
| alerts.timer | Каждые 2 часа | Проверка ошибок и алертинг | Включен |

## Расписание алертов

### Типы алертов

1. **Ошибки задач** - при неудачных запусках загрузчиков
2. **Устаревшие данные** - при отставании более 2 дней
3. **Проблемы со здоровьем** - при проблемах с системой

### Настройка

```bash
# Настройка SMTP
cp configs/.env.alerts.sample secrets/.env.alerts
# Заполните SMTP_HOST, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO

# Запуск проверки
python3 ops/alerts/notify.py --check-errors --check-freshness
```

## Расписание smoke-тестов

### Проверяемые компоненты

1. **Инфраструктура** - подключение к ClickHouse, наличие таблиц
2. **Данные** - свежесть, качество, отсутствие дубликатов
3. **Процессы** - статус запусков задач, алерты

### Запуск

```bash
# Базовый запуск
python3 ops/smoke_test_integrations.py

# С сохранением результатов
python3 ops/smoke_test_integrations.py --output results.json

# Через обертку
./ops/run_smoke_test.sh run-with-results
```

**Документация**: [ops/SMOKE_TEST.md](../SMOKE_TEST.md)

## Расписание healthcheck

### Эндпоинты

- `/healthz` - базовая проверка здоровья
- `/healthz/detailed` - детальная проверка с метриками
- `/healthz/freshness` - проверка свежести данных

### Пример ответа

```json
{
  "status": "ok",
  "timestamp": "2023-10-12T10:00:00+03:00",
  "checks": {
    "clickhouse": "ok",
    "data_freshness": {
      "qtickets": {
        "status": "ok",
        "latest_date": "2023-10-12",
        "days_behind": 0
      }
    }
  }
}
```

## Расписание DDL

### Основные таблицы

- `stg_qtickets_sales_raw` - сырые данные о продажах QTickets
- `dim_events` - справочник мероприятий QTickets
- `fact_vk_ads_daily` - статистика VK Ads
- `fact_direct_daily` - статистика Яндекс.Директ

### Витрины

- `v_sales_latest` - актуальные данные о продажах без дублей
- `v_marketing_daily` - сводная статистика по маркетингу
- `v_romi_kpi` - ROMI KPI с цветовой индикацией
- `v_campaign_performance` - эффективность рекламных кампаний

**Документация**: [infra/clickhouse/init_integrations.sql](../infra/clickhouse/init_integrations.sql)

## Расписание конфигурации

### Переменные окружения

Каждый загрузчик использует свой файл конфигурации:

- `.env.qtickets` - QTickets API
- `.env.vk` - VK Ads API
- `.env.direct` - Яндекс.Директ API
- `.env.gmail` - Gmail API
- `.env.ch` - ClickHouse
- `.env.alerts` - Алерты

### Шаблоны

Шаблоны конфигурации находятся в `configs/`:

- `.env.qtickets.sample`
- `.env.vk.sample`
- `.env.direct.sample`
- `.env.gmail.sample`
- `.env.ch.sample`
- `.env.alerts.sample`

## Расписание runbook

### Основные операции

- **Запуск загрузчиков**: [docs/RUNBOOK_INTEGRATIONS.md](../docs/RUNBOOK_INTEGRATIONS.md)
- **Управление таймерами**: [ops/systemd/README.md](../ops/systemd/README.md)
- **Мониторинг**: [ops/alerts/README.md](../ops/alerts/README.md)
- **Резервное копирование**: [docs/RUNBOOK_BACKUP_RESTORE.md](../docs/RUNBOOK_BACKUP_RESTORE.md)

### Устранение неполадок

- **Проблемы с QTickets**: проверка токена, API доступности
- **Проблемы с VK Ads**: проверка токена, прав доступа к кабинетам
- **Проблемы с Яндекс.Директ**: проверка токена, формата отчетов
- **Проблемы с Gmail**: проверка OAuth2, прав доступа

## Расписание архитектуры

### Потоки данных

1. **QTickets API → ClickHouse** (каждые 15 минут)
2. **VK Ads API → ClickHouse** (ежедневно 00:00 MSK)
3. **Яндекс.Директ API → ClickHouse** (ежедневно 00:10 MSK)
4. **Gmail API → ClickHouse** (каждые 4 часа, отключен)

### Идемпотентность

Все загрузчики идемпотентны благодаря:
- `ReplacingMergeTree` с `_ver` для удаления старых версий
- Уникальным ключам в витринах
- Хешированию строк для дедупликации

### Безопасность

- Секреты хранятся в `secrets/` (в .gitignore)
- Переменные окружения загружаются из защищенных файлов
- Ролевая модель доступа в ClickHouse
- Аудит и логирование всех операций

## Расписание changelog

### Версия 1.0.0 (2025-10-12)

- Полноценная сквозная интеграция всех источников данных
- Единый модуль `integrations/common/` с утилитами
- Системные таймеры для автоматического запуска
- Healthcheck сервер с HTTP эндпоинтами
- Система алертов с email уведомлениями
- Smoke-проверки для контроля качества данных
- Дашборд DataLens с ROMI-светофором

**Полный changelog**: [CHANGELOG.md](../CHANGELOG.md)

## Заключение

Система интеграций Zakaz Dashboard обеспечивает надежную и автоматизированную загрузку данных из различных источников в ClickHouse для анализа в DataLens. Единая архитектура, comprehensive мониторинг и автоматизированное тестирование гарантируют стабильность и качество данных.