# Инструкция по запуску E2E тестирования QTickets API

## Обзор

Этот документ описывает процесс запуска сквозного тестирования пайплайна QTickets API на сервере museshow перед выкладкой на прод клиента.

## Подготовка

1. Подключитесь к серверу museshow под пользователем `etl` или `root`:

```bash
ssh etl@museshow
# или
ssh root@museshow
```

2. Перейдите в директорию проекта:

```bash
cd /opt/zakaz_dashboard/dashboard-mvp
```

3. Убедитесь, что вы находитесь в актуальной ветке кода:

```bash
git status
git pull origin main
```

## Запуск тестирования

Для автоматического выполнения всех шагов E2E тестирования используйте подготовленный скрипт:

```bash
chmod +x e2e_qtickets_api_test.sh
./e2e_qtickets_api_test.sh
```

Скрипт выполнит следующие шаги:

1. **Проверка окружения** - убедится, что контейнеры ClickHouse запущены
2. **Применение миграции** - создаст необходимые таблицы для QTickets API
3. **Создание конфигурации** - создаст секретный env файл с реальными данными
4. **Настройка прав доступа** - предоставит необходимые права пользователю etl_writer
5. **Запуск лоадера** - выполнит загрузку данных из QTickets API
6. **Проверка данных** - проверит наличие данных в ClickHouse таблицах
7. **Проверка healthcheck** - проверит работоспособность healthcheck
8. **Настройка systemd** - настроит и протестирует systemd таймер
9. **Smoke-проверки** - выполнит проверки качества данных
10. **Генерация отчёта** - создаст подробный отчёт о результатах тестирования

## Ручное выполнение (опционально)

Если вы хотите выполнить шаги тестирования вручную, следуйте инструкциям ниже:

### Шаг 1. Проверка окружения

```bash
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
docker compose ps
```

Убедитесь, что контейнеры `ch-zakaz` и `ch-zakaz-caddy` в статусе `Up`.

### Шаг 2. Применение миграции

```bash
cd /opt/zakaz_dashboard/dashboard-mvp
docker exec -i ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  < infra/clickhouse/migrations/2025-qtickets-api.sql
```

### Шаг 3. Создание секретного env файла

```bash
mkdir -p /opt/zakaz_dashboard/dashboard-mvp/secrets
nano /opt/zakaz_dashboard/dashboard-mvp/secrets/.env.qtickets_api
```

Содержимое файла:

```env
# QTickets API config
QTICKETS_API_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_API_TOKEN=4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ
QTICKETS_ORG_SLUG=irs-prod
QTICKETS_ORG_DASHBOARD_URL=https://irs-prod.qtickets.ru

# ClickHouse connection for ETL writer
CLICKHOUSE_HOST=http://localhost:8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=etl_writer_password_2024

# Runtime
TZ=Europe/Moscow
ORG_NAME=irs-prod
```

### Шаг 4. Настройка прав доступа

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "GRANT INSERT ON zakaz.stg_qtickets_api_orders_raw TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "GRANT INSERT ON zakaz.stg_qtickets_api_inventory_raw TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "GRANT INSERT ON zakaz.dim_events TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "GRANT INSERT ON zakaz.fact_qtickets_sales_daily TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "GRANT INSERT ON zakaz.fact_qtickets_inventory_latest TO etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "GRANT INSERT ON zakaz.meta_job_runs TO etl_writer"
```

### Шаг 5. Запуск лоадера

```bash
cd /opt/zakaz_dashboard/dashboard-mvp

# Активация виртуального окружения
source .venv/bin/activate || python3 -m venv .venv && source .venv/bin/activate

# Установка зависимостей
pip install -q clickhouse-driver requests python-dotenv

# Запуск лоадера
python -m integrations.qtickets_api.loader \
  --envfile /opt/zakaz_dashboard/dashboard-mvp/secrets/.env.qtickets_api \
  --since-hours 24 \
  --verbose
```

### Шаг 6. Проверка данных в ClickHouse

```bash
# Проверка staging таблицы
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "SELECT count(*) AS rows, max(sale_ts) AS last_sale FROM zakaz.stg_qtickets_api_orders_raw"

# Проверка fact таблицы
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "SELECT sales_date, city, sum(tickets_sold) AS sold, sum(revenue) AS rev
      FROM zakaz.fact_qtickets_sales_daily
      GROUP BY sales_date, city
      ORDER BY sales_date DESC
      LIMIT 10"

# Проверка витрины
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  -q "SELECT * FROM zakaz.v_sales_latest LIMIT 20"
```

### Шаг 7. Проверка healthcheck

```bash
cd /opt/zakaz_dashboard/dashboard-mvp
python ops/healthcheck_integrations.py --env secrets/.env.ch --check qtickets_api
```

### Шаг 8. Настройка systemd

```bash
# Копирование юнитов
sudo cp ops/systemd/qtickets_api.service /etc/systemd/system/
sudo cp ops/systemd/qtickets_api.timer /etc/systemd/system/

# Перезагрузка и запуск
sudo systemctl daemon-reload
sudo systemctl enable --now qtickets_api.timer

# Проверка статуса
sudo systemctl status qtickets_api.timer

# Принудительный запуск
sudo systemctl start qtickets_api.service
sudo systemctl status qtickets_api.service
journalctl -u qtickets_api.service -n 50 --no-pager
```

### Шаг 9. Smoke-проверки

```bash
docker exec -i ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='AdminMin2024!Strong#Pass' \
  < infra/clickhouse/smoke_checks_qtickets_api.sql
```

## Анализ результатов

После выполнения тестирования будет создан отчёт `TASK-QT-API-E2E-REPORT.md` в корне проекта. Отчёт содержит:

- Результаты каждого шага тестирования
- Выводы SQL запросов к ClickHouse
- Логи работы лоадера и systemd сервиса
- Финальное заключение о готовности пайплайна к выкладке

## Критерии готовности

Пайплайн считается готовым к выкладке если:

1. Миграция применена без ошибок
2. Лоадер успешно загрузил данные из QTickets API
3. Данные присутствуют в ClickHouse таблицах
4. Healthcheck показывает статус `ok`
5. Systemd сервис корректно настроен и работает
6. Smoke-проверки качества данных пройдены

## Возможные проблемы и решения

### Проблема: Ошибка прав доступа

**Симптом:** Ошибка `ACCESS_DENIED` при вставке данных

**Решение:** Убедитесь, что пользователю `etl_writer` предоставлены права на вставку во все таблицы:

```sql
GRANT INSERT ON zakaz.* TO etl_writer
```

### Проблема: Ошибка в витрине v_sales_latest

**Симптом:** SQL ошибка при запросе к витрине

**Решение:** Проверьте синтаксис CREATE VIEW в миграции и при необходимости исправьте:

```sql
DROP VIEW IF EXISTS zakaz.v_sales_latest;
-- Исправленный CREATE VIEW...
```

### Проблема: Лоадер не может подключиться к QTickets API

**Симптом:** Ошибка аутентификации или подключения

**Решение:** Проверьте токен в `.env.qtickets_api` и доступность API:

```bash
curl -H "Authorization: Bearer 4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ" \
  https://qtickets.ru/api/rest/v1/events
```

## Следующие шаги

После успешного прохождения E2E тестирования:

1. Зафиксируйте результаты в git:
   ```bash
   git add TASK-QT-API-E2E-REPORT.md
   git commit -m "feat: E2E тестирование QTickets API пройдено успешно"
   ```

2. Подготовьте план развертывания на сервере заказчика

3. Выполните развертывание на проде заказчика