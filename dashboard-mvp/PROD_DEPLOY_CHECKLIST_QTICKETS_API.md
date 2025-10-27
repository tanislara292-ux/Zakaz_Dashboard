# PROD_DEPLOY_CHECKLIST_QTICKETS_API.md

## Чек-лист развертывания QTickets API на продакшен сервере

> **Важно:** Все команды выполняются от пользователя с правами sudo или root
> 
> **Предварительное требование:** Docker и Docker Compose должны быть установлены на сервере

---

### Шаг 1. Подготовка репозитория

- [ ] Скопировать актуальный репозиторий в `/opt/zakaz_dashboard/dashboard-mvp`

```bash
# Пример для git репозитория
sudo -u etl git clone <repository_url> /opt/zakaz_dashboard/dashboard-mvp
cd /opt/zakaz_dashboard/dashboard-mvp
sudo -u etl git checkout <production_branch>

# Установить правильные права
sudo chown -R etl:etl /opt/zakaz_dashboard
sudo chmod 755 /opt/zakaz_dashboard
```

- [ ] Убедиться, что директория `secrets` существует:

```bash
sudo -u etl mkdir -p /opt/zakaz_dashboard/secrets
sudo chmod 700 /opt/zakaz_dashboard/secrets
```

---

### Шаг 2. Настройка секретов

- [ ] Создать файл `/opt/zakaz_dashboard/secrets/.env.qtickets_api`:

```bash
sudo -u etl touch /opt/zakaz_dashboard/secrets/.env.qtickets_api
sudo chmod 600 /opt/zakaz_dashboard/secrets/.env.qtickets_api
```

- [ ] Заполнить файл следующими переменными:

```bash
# QTickets API конфигурация
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
# Или для кастомного домена: QTICKETS_BASE_URL=https://irs-prod.qtickets.ru/api/rest/v1
QTICKETS_TOKEN=<ваш_боевой_токен>

# ClickHouse конфигурация
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=<пароль_etl_writer>
CLICKHOUSE_DATABASE=zakaz

# Системные настройки
TZ=Europe/Moscow
ORG_NAME=zakaz
```

- [ ] Проверить корректность файла:

```bash
sudo -u etl cat /opt/zakaz_dashboard/secrets/.env.qtickets_api
```

---

### Шаг 3. Применение миграции ClickHouse

- [ ] Применить финальную миграцию:

```bash
cd /opt/zakaz_dashboard/dashboard-mvp

# Используем администратора ClickHouse для миграций
docker exec -i ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  < infra/clickhouse/migrations/2025-qtickets-api-final.sql
```

- [ ] Проверить, что таблицы созданы:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  -q "SHOW TABLES FROM zakaz LIKE 'qtickets%'"
```

- [ ] Проверить права доступа:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  -q "SHOW GRANTS FOR etl_writer"
```

---

### Шаг 4. Сборка Docker-образа

- [ ] Собрать Docker-образ qtickets_api:

```bash
cd /opt/zakaz_dashboard/dashboard-mvp
docker build -t qtickets_api:latest integrations/qtickets_api
```

- [ ] Проверить, что образ собрался:

```bash
docker images | grep qtickets_api
```

- [ ] Проверить размер образа (должен быть < 200MB):

```bash
docker images qtickets_api:latest --format "table {{.Repository}}\t{{.Size}}"
```

---

### Шаг 5. Ручной пробный запуск (dry-run)

- [ ] Запустить контейнер в dry-run режиме:

```bash
cd /opt/zakaz_dashboard/dashboard-mvp

docker run --rm \
  --name qtickets_api_test \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run
```

**Ожидаемый результат:**
- Статус 200 от `/orders`
- Логи "Fetched orders from QTickets API via GET"
- Логи "Transformed N sales rows"
- Вывод summary в конце:
  ```
  [qtickets_api] Dry-run complete:
    Events: N
    Orders: N
    Sales rows: N
    Inventory shows processed: N
  ```

- [ ] Проверить логи на наличие ошибок:

```bash
# Если контейнер упал, посмотреть логи
docker logs qtickets_api_test
```

---

### Шаг 6. Установка systemd юнитов

- [ ] Скопировать файлы юнитов в systemd:

```bash
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/qtickets_api.service /etc/systemd/system/
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/qtickets_api.timer /etc/systemd/system/
```

- [ ] Перезагрузить systemd конфигурацию:

```bash
sudo systemctl daemon-reload
```

- [ ] Включить и запустить таймер:

```bash
sudo systemctl enable --now qtickets_api.timer
```

---

### Шаг 7. Проверка работы systemd

- [ ] Проверить статус таймера:

```bash
systemctl status qtickets_api.timer
systemctl list-timers qtickets_api.*
```

- [ ] Запустить сервис вручную для проверки:

```bash
sudo systemctl start qtickets_api.service
```

- [ ] Проверить логи запуска:

```bash
# Последние запуски
journalctl -u qtickets_api.service --no-pager --since "5 min ago"

# Отслеживание в реальном времени
journalctl -u qtickets_api.service -f
```

- [ ] Проверить, что Docker контейнер запускается:

```bash
docker ps -a --filter "name=qtickets_api_"
```

---

### Шаг 8. Проверка данных в ClickHouse

- [ ] Проверить, что появились новые строки в стейджинг таблице:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_orders_raw WHERE sale_ts > now() - INTERVAL 1 DAY;"
```

- [ ] Проверить свежесть данных:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  -q "SELECT max(sale_ts) as latest_order FROM zakaz.stg_qtickets_api_orders_raw;"
```

- [ ] Проверить агрегированные данные:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  -q "SELECT count() FROM zakaz.fact_qtickets_sales_daily WHERE sales_date = today();"
```

- [ ] Проверить инвентарь:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  -q "SELECT count() FROM zakaz.fact_qtickets_inventory_latest WHERE snapshot_ts > now() - INTERVAL 2 HOUR;"
```

---

### Шаг 9. Проверка smoke-чеков

- [ ] Запустить smoke-проверки:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  < infra/clickhouse/smoke_checks_qtickets_api.sql
```

**Ожидаемые результаты:**
- Все таблицы существуют
- Нет отрицательных значений revenue/tickets
- Данные свежие (последние 48 часов)
- Минимум дубликатов в стейджинге
- Витрина `v_qtickets_sales_dashboard` содержит данные

---

### Шаг 10. Проверка DataLens доступа

- [ ] Проверить, что DataLens может читать данные:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader \
  --password='<datalens_password>' \
  -q "SELECT count() FROM zakaz.v_qtickets_sales_dashboard LIMIT 1;"
```

- [ ] Проверить доступ к основным таблицам:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader \
  --password='<datalens_password>' \
  -q "SHOW TABLES FROM zakaz LIKE 'vtickets%';"
```

---

### Шаг 11. Финальная валидация

- [ ] Проверить, что таймер работает по расписанию (подождать 15 минут):

```bash
# Через 15 минут после включения таймера
journalctl -u qtickets_api.service --since "15 minutes ago" --no-pager
```

- [ ] Проверить метаданные запусков в ClickHouse:

```bash
docker exec ch-zakaz clickhouse-client \
  --user=admin_min \
  --password='<admin_password>' \
  -q "SELECT job, status, started_at, message FROM zakaz.meta_job_runs WHERE job = 'qtickets_api' ORDER BY started_at DESC LIMIT 5;"
```

- [ ] Проверить здоровье системы:

```bash
# Статус всех таймеров
/opt/zakaz_dashboard/dashboard-mvp/ops/systemd/manage_timers.sh status

# Проверка свободного места
df -h

# Проверка Docker
docker system df
```

---

## Траблшутинг

### Если GET /orders возвращает ошибку:

1. **Проверить токен:**
```bash
curl -H "Authorization: Bearer <token>" \
     -H "Accept: application/json" \
     "https://qtickets.ru/api/rest/v1/orders?limit=1"
```

2. **Проверить BASE_URL:**
```bash
# Попробовать альтернативный URL
curl -H "Authorization: Bearer <token>" \
     "https://qtickets.ru/api/rest/v1/events?limit=1"
```

### Если контейнер не запускается:

1. **Проверить образ:**
```bash
docker run --rm qtickets_api:latest python --version
```

2. **Проверить переменные окружения:**
```bash
docker run --rm --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api qtickets_api:latest env | grep QTICKETS
```

### Если нет данных в ClickHouse:

1. **Проверить права ETL пользователя:**
```bash
docker exec ch-zakaz clickhouse-client \
  --user=etl_writer \
  --password='<etl_password>' \
  -q "SHOW GRANTS"
```

2. **Проверить подключение:**
```bash
docker exec ch-zakaz clickhouse-client \
  --user=etl_writer \
  --password='<etl_password>' \
  -q "SELECT 1"
```

---

## Мониторинг после развертывания

### Ежедневные проверки:

1. **Свежесть данных:**
```sql
SELECT 
    max(sale_ts) as latest_order,
    today() - toDate(max(sale_ts)) as days_stale
FROM zakaz.stg_qtickets_api_orders_raw;
```

2. **Ошибки в запусках:**
```sql
SELECT * FROM zakaz.meta_job_runs 
WHERE job = 'qtickets_api' 
  AND status = 'failed' 
  AND started_at > today() - INTERVAL 1 DAY;
```

3. **Объемы данных:**
```sql
SELECT 
    toDate(sale_ts) as date,
    count() as orders,
    sum(revenue) as total_revenue
FROM zakaz.stg_qtickets_api_orders_raw
WHERE sale_ts > today() - INTERVAL 7 DAY
GROUP BY date
ORDER BY date DESC;
```

### Алерты для настройки:

- Нет данных более 2 часов
- Больше 5% неудачных запусков за день
- Резкое падение объема заказов (>50% compared to yesterday)

---

## Готовность к продакшену

После выполнения всех шагов чек-листа:

✅ **QTickets API интеграция развернута**
✅ **Данные поступают каждые 15 минут**
✅ **ClickHouse таблицы заполнены**
✅ **DataLens имеет доступ к витринам**
✅ **Мониторинг настроен**
✅ **Секреты защищены**

**Статус: ПРОДАКШЕН ГОТОВ ✅**

Можем сказать заказчику: "данные с вашего билета-продавца QTickets прилетают к вам в ClickHouse каждые 15 минут, DataLens читает витрины, дашборд живёт".