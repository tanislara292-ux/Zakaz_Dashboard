# ClickHouse Infrastructure

## Развертывание

### 1. Подготовка окружения

Скопируйте `.env.sample` в `.env` и установите пароли:

```bash
cp ../../.env.sample ../../.env
# Отредактируйте .env, установите CLICKHOUSE_*_PASSWORD
```

### 2. Запуск ClickHouse

```bash
cd infra/clickhouse
docker compose up -d
```

### 3. Инициализация БД и таблиц

```bash
# Выполните init.sql от имени admin
docker exec -i ch-zakaz clickhouse-client --user=admin --password=$CLICKHOUSE_ADMIN_PASSWORD < init.sql
```

### 4. Проверка работоспособности

```bash
# Проверка версии
docker exec -it ch-zakaz clickhouse-client -q "SELECT version()"

# Проверка таблиц
docker exec -it ch-zakaz clickhouse-client -q "SHOW TABLES FROM zakaz"
```

## Структура

- `docker-compose.yml` - конфигурация Docker Compose для ClickHouse и Caddy
- `Caddyfile` - конфигурация реверс-прокси для HTTPS доступа
- `users.d/10-users.xml` - настройки пользователей и профилей доступа
- `init.sql` - DDL для создания БД, таблиц и представлений для DataLens
- `smoke_checks.sql` - SQL-проверки для контроля качества данных

## Пользователи

- **admin** - полные права (пароль из `CLICKHOUSE_ADMIN_PASSWORD`)
- **etl_writer** - INSERT/SELECT на все таблицы (пароль из `CLICKHOUSE_ETL_WRITER_PASSWORD`)
- **datalens_reader** - SELECT на все таблицы (пароль из `CLICKHOUSE_DATALENS_READER_PASSWORD`)

## Таблицы

### Стейджинг (stg_*)
- `stg_qtickets_sales` - сырые данные о продажах QTickets с дедупликацией
- `stg_vk_ads_daily` - суточная статистика VK Ads

### Ядро (core_*)
- `core_sales_fct` - фактовая таблица продаж (каркас для будущей логики)

### Представления для DataLens (v_*)
- `v_sales_latest` - основное представление по продажам без дублей
- `v_sales_14d` - агрегированные данные за 14 дней для быстрых графиков

## Дедупликация

Для стейджинг-таблиц используется `ReplacingMergeTree(ingested_at)` с одинаковым PK.
Для консистентных выборок используйте `FINAL` в запросах:

```sql
SELECT * FROM zakaz.stg_qtickets_sales FINAL WHERE report_date >= today() - 7;
```

## Остановка и удаление

```bash
# Остановка с сохранением данных
docker compose down

# Полное удаление (включая данные)
docker compose down -v
```

## Подключение извне

### Локальное подключение
- HTTP интерфейс: `http://localhost:8123`
- Native интерфейс: `localhost:9000`

### Production подключение (DataLens)
- HTTPS интерфейс через реверс-прокси: `https://ch.your-domain`
- Порт: 443 (HTTPS)
- База данных: `zakaz`
- Пользователь: `datalens_reader`

Для production-развертывания используется реверс-прокси Caddy с автоматическим TLS от Let's Encrypt.

## Настройка HTTPS доступа

1. Укажите ваш домен в `Caddyfile` вместо `ch.your-domain`
2. Запустите контейнеры:
   ```bash
   docker compose up -d
   ```
3. Проверьте доступность:
   ```bash
   curl -I https://ch.your-domain/?query=SELECT%201
   ```

## DataLens подключение

Подробная инструкция по настройке подключения DataLens к ClickHouse доступна в `../../docs/RUNBOOK_DATALENS.md`.

Краткие шаги:
1. Создайте подключение `ch_zakaz_prod` в DataLens
2. Создайте источник `src_ch_sales_latest` на основе `v_sales_latest`
3. Создайте датасет `ds_sales`
4. Создайте дашборд `Zakaz — Sales (MVP)`