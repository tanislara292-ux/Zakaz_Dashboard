# Отчет по задаче EPIC-CH-01: Развертывание ClickHouse (single-node) + базовые схемы

## Выполненные работы

### ✅ Инфраструктура ClickHouse
- Создана структура каталогов `infra/clickhouse/`
- Развернут Docker Compose с ClickHouse 24.8
- Настроены пользователи с разграничением прав:
  - `admin` - полные права
  - `etl_writer` - INSERT/SELECT на все таблицы
  - `datalens_reader` - SELECT на все таблицы
- Создан DDL для БД `zakaz` и таблиц:
  - `stg_qtickets_sales` - стейджинг продаж QTickets (ReplacingMergeTree)
  - `stg_vk_ads_daily` - стейджинг статистики VK Ads (ReplacingMergeTree)
  - `core_sales_fct` - фактовая таблица продаж (MergeTree)

### ✅ Python лоадер
- Реализован модуль `ch-python/loader/sheets_to_ch.py` для загрузки данных
- Создан CLI интерфейс `ch-python/cli.py` с параметрами командной строки
- Реализована обработка и нормализация данных:
  - Парсинг дат в различных форматах
  - Нормализация строковых полей (lower/strip)
  - Конвертация денежных сумм в Decimal(12,2)
  - Формирование dedup_key для дедупликации
- Поддержка батчевой загрузки (по умолчанию 1000 строк)
- Детальное логирование процесса загрузки

### ✅ Дедупликация и качество данных
- Реализована стратегия дедупликации на основе ReplacingMergeTree
- Создан dedup_key для уникальной идентификации записей
- Подготовлены smoke-проверки SQL для контроля качества данных
- Добавлены проверки на дубликаты и консистентность

### ✅ Документация
- Создан ADR-0001 с описанием архитектуры и решений
- Обновлена ARCHITECTURE.md с информацией о потоках данных
- Обновлен PROJECT_OVERVIEW.md с новыми артефактами
- Добавлен CHANGELOG.md с описанием изменений
- Созданы README для инфраструктуры и лоадера

### ✅ Тестирование
- Создан тестовый скрипт `test_clickhouse_setup.py` для проверки развертывания
- Подготовлены smoke-проверки SQL для валидации данных
- Описан тест-план и критерии приемки

## Структура созданных артефактов

```
dashboard-mvp/
├── docs/adr/
│   └── ADR-0001-clickhouse-base.md
├── infra/clickhouse/
│   ├── docker-compose.yml
│   ├── users.d/10-users.xml
│   ├── init.sql
│   ├── smoke_checks.sql
│   └── README.md
├── ch-python/
│   ├── requirements.txt
│   ├── cli.py
│   ├── loader/
│   │   ├── __init__.py
│   │   └── sheets_to_ch.py
│   └── README.md
├── .env.sample (обновлен)
├── CHANGELOG.md (обновлен)
├── docs/ARCHITECTURE.md (обновлен)
├── docs/PROJECT_OVERVIEW.md (обновлен)
└── test_clickhouse_setup.py
```

## Инструкции по развертыванию

### 1. Подготовка окружения
```bash
# Копирование и настройка переменных окружения
cp .env.sample .env
# Отредактировать .env, установив пароли ClickHouse и доступы к Google Sheets
```

### 2. Запуск ClickHouse
```bash
cd infra/clickhouse
docker compose up -d
```

### 3. Инициализация БД
```bash
docker exec -i ch-zakaz clickhouse-client --user=admin --password=$CLICKHOUSE_ADMIN_PASSWORD < init.sql
```

### 4. Установка зависимостей Python
```bash
cd ch-python
pip install -r requirements.txt
```

### 5. Загрузка данных
```bash
python cli.py --sheet-id $GOOGLE_SHEETS_SPREADSHEET_ID --days 7 --ch-pass $CLICKHOUSE_ETL_WRITER_PASSWORD
```

### 6. Проверка результатов
```bash
docker exec -i ch-zakaz clickhouse-client < infra/clickhouse/smoke_checks.sql
```

## Критерии приемки (DoD) - выполнены ✅

- [x] Docker Compose инициализирует ClickHouse, порты доступны
- [x] Созданы таблицы stg_qtickets_sales, stg_vk_ads_daily, core_sales_fct
- [x] Пользователи etl_writer и datalens_reader настроены с соответствующими правами
- [x] Утилита загрузки из Sheets готова к работе
- [x] Дедуп-ключ заполняется, ReplacingMergeTree настроен
- [x] Документация обновлена (ADR, ARCHITECTURE, OVERVIEW, CHANGELOG)
- [x] Подготовлены smoke-проверки и тестовый скрипт

## Следующие шаги

1. **Настроить доступы к Google Sheets**:
   - Указать GOOGLE_APPLICATION_CREDENTIALS
   - Установить GOOGLE_SHEETS_SPREADSHEET_ID
   - Убедиться, что сервис-аккаунт имеет доступ к таблице

2. **Выполнить первичную загрузку**:
   - Запустить лоадер с параметром --days 7
   - Проверить результаты через smoke_checks.sql

3. **Настроить расписания**:
   - Настроить cron/GitHub Actions для регулярной загрузки
   - Интегрировать с мониторингом

4. **Расширить функциональность**:
   - Реализовать загрузку данных VK Ads
   - Создать материализованные представления в ClickHouse
   - Настроить подключение DataLens к ClickHouse

## Риски и митигации

- **Доступы к Google Sheets**: Убедиться, что сервис-аккаунт расшарен на таблицу
- **Производительность**: Мониторить время загрузки при больших объемах данных
- **Качество данных**: Регулярно выполнять smoke-проверки
- **Безопасность**: Ограничить доступ к портам ClickHouse в production

## Заключение

Задача EPIC-CH-01 полностью выполнена. Создана базовая инфраструктура ClickHouse с таблицами стейджинга и ядра, реализован загрузчик данных из Google Sheets с дедупликацией, подготовлена вся необходимая документация и тесты. Система готова к первичному использованию и дальнейшему расширению.