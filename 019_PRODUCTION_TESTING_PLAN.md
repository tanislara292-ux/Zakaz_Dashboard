# План тестирования в боевом режиме для задачи 019

**Дата:** 2025-10-30  
**Цель:** Полная верификация работоспособности системы перед передачей заказчику  

---

## 🔄 Подготовка тестового окружения

### 1. Очистка и подготовка чистого хоста

```bash
# Остановка всех контейнеров
docker stop $(docker ps -aq) 2>/dev/null || true

# Удаление всех контейнеров
docker rm $(docker ps -aq) 2>/dev/null || true

# Очистка системы
docker system prune -f

# Удаление старых volumes (если есть)
docker volume prune -f

# Проверка чистоты
docker ps -a
docker images
docker volume ls
```

### 2. Подготовка конфигурационных файлов

```bash
# Клонирование свежей копии репозитория
git clone <repository_url> /tmp/zakaz_test
cd /tmp/zakaz_test/dashboard-mvp

# Подготовка ClickHouse конфигурации
cd infra/clickhouse
cp .env.example .env

# Подготовка Qtickets конфигурации
cd ../..
cp configs/.env.qtickets_api.sample secrets/.env.qtickets_api
# Редактировать secrets/.env.qtickets_api с реальными данными
```

---

## 🧪 Этап 1: Тестирование ClickHouse RBAC

### 1.1 Bootstrap тест

```bash
cd /tmp/zakaz_test/dashboard-mvp/infra/clickhouse
../../scripts/bootstrap_clickhouse.sh
```

**Ожидаемый результат:**
- Контейнер `ch-zakaz` запускается и становится healthy
- Все таблицы из REQUIRED_TABLES созданы
- Роли и гранты применены успешно

### 1.2 Проверка пользователей и ролей

```bash
# Проверка admin пользователя
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SHOW GRANTS FOR admin"

# Проверка service пользователей
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SHOW GRANTS FOR etl_writer"

docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SHOW GRANTS FOR datalens_reader"

docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SHOW GRANTS FOR backup_user"
```

**Ожидаемый результат:**
- admin: GRANT ALL ON *.* WITH GRANT OPTION
- etl_writer: SELECT, INSERT на zakaz.*, SELECT на meta.*
- datalens_reader: SELECT на zakaz.*, meta.*, bi.*, system.*
- backup_user: SELECT на zakaz.*, SELECT, INSERT на meta.backup_runs

### 1.3 Тестирование прав доступа

```bash
# Тест etl_writer (должен иметь INSERT права)
docker exec ch-zakaz clickhouse-client \
  --user=etl_writer --password=EtL2024!Strong#Pass \
  -q "INSERT INTO zakaz.meta_job_runs VALUES (now(), 'test', 'ok', now(), now(), 1, '{}')"

# Тест datalens_reader (только SELECT)
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader --password=ChangeMe123! \
  -q "SELECT * FROM zakaz.meta_job_runs LIMIT 1"

# Попытка INSERT должна провалиться
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader --password=ChangeMe123! \
  -q "INSERT INTO zakaz.meta_job_runs VALUES (now(), 'test', 'ok', now(), now(), 1, '{}')" || echo "Expected failure"
```

### 1.4 DataLens HTTP доступ

```bash
cd /tmp/zakaz_test/dashboard-mvp
../../scripts/bootstrap_datalens.sh
```

**Ожидаемый результат:**
- SELECT 1 выполняется успешно
- Подсчет таблиц в zakaz работает
- SHOW GRANTS FOR datalens_reader показывает правильные права

---

## 🚀 Этап 2: Тестирование Qtickets API интеграции

### 2.1 Dry-run тест

```bash
cd /tmp/zakaz_test/dashboard-mvp
./scripts/smoke_qtickets_dryrun.sh --env-file secrets/.env.qtickets_api
```

**Ожидаемый результат:**
- Контейнер завершается с кодом 0
- В логах упомянут stub режим
- Нет записей в zakaz.meta_job_runs

### 2.2 Production тест

```bash
# Установить DRY_RUN=false в secrets/.env.qtickets_api
# Убедиться что QTICKETS_TOKEN и ORG_NAME установлены

# Сборка образа
docker build -f integrations/qtickets_api/Dockerfile -t qtickets_api:test .

# Запуск в production режиме
docker run --rm \
  --network clickhouse_default \
  --env-file secrets/.env.qtickets_api \
  --name qtickets_test_$(date +%Y%m%d%H%M%S) \
  qtickets_api:test
```

### 2.3 Проверка результатов

```bash
# Проверка meta_job_runs
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT status, message FROM zakaz.meta_job_runs ORDER BY finished_at DESC LIMIT 5 FORMAT PrettyCompact"

# Проверка данных в таблицах
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_orders_raw"

docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count() FROM zakaz.fact_qtickets_sales_daily"

# Проверка inventory (если реализовано)
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_inventory_raw"
```

---

## 🧪 Этап 3: Юнит-тесты и валидация

### 3.1 Запуск юнит-тестов

```bash
cd /tmp/zakaz_test/dashboard-mvp
python -m pip install -r integrations/qtickets_api/requirements.txt
pip install pytest
pytest integrations/qtickets_api/tests/ -v
```

**Ожидаемый результат:**
- Все тесты проходят
- Покрытие ключевых компонентов

### 3.2 Валидация схемы

```bash
# Запуск валидатора схемы
python scripts/validate_clickhouse_schema.py

# Или с параметрами
python scripts/validate_clickhouse_schema.py \
  --host localhost \
  --port 9000 \
  --user admin \
  --password admin_pass
```

**Ожидаемый результат:**
- Все REQUIRED_TABLES существуют
- Все view definitions корректны
- Гранты соответствуют ожиданиям

---

## 🔥 Этап 4: CI/CD тестирование

### 4.1 Локальный CI тест

```bash
# Симуляция CI pipeline
cd /tmp/zakaz_test/dashboard-mvp

# Setup Python
python -m pip install -r integrations/qtickets_api/requirements.txt
pip install pytest

# Запуск валидации схемы
python scripts/validate_clickhouse_schema.py

# Запуск тестов
pytest integrations/qtickets_api/tests/ -v

# Сборка Docker образа
docker build -f integrations/qtickets_api/Dockerfile -t qtickets_api:ci-test .
```

### 4.2 GitHub Actions тест

```bash
# Пуш ветки для тестирования CI
git checkout -b test-ci-019
git add .
git commit -m "test: CI pipeline verification"
git push origin test-ci-019

# Проверить выполнение в GitHub Actions
```

---

## 🚨 Этап 5: Тестирование отказов

### 5.1 Сетевые сбои

```bash
# Симуляция потери сети во время работы loader
docker run --rm \
  --network clickhouse_default \
  --env-file secrets/.env.qtickets_api \
  --name qtickets_failure_test \
  qtickets_api:test &
LOADER_PID=$!

# Ожидание начала работы
sleep 10

# Временное отключение сети
docker network disconnect clickhouse_default qtickets_failure_test
sleep 5
docker network connect clickhouse_default qtickets_failure_test

# Ожидание завершения
wait $LOADER_PID

# Проверка логов на предмет retry логики
docker logs qtickets_failure_test
```

### 5.2 Ошибки аутентификации

```bash
# Тест с неверным токеном
cp secrets/.env.qtickets_api secrets/.env.qtickets_api.bad
sed -i 's/QTICKETS_TOKEN=.*/QTICKETS_TOKEN=invalid_token/' secrets/.env.qtickets_api.bad

docker run --rm \
  --network clickhouse_default \
  --env-file secrets/.env.qtickets_api.bad \
  qtickets_api:test

# Проверка обработки ошибок в meta_job_runs
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT status, message FROM zakaz.meta_job_runs ORDER BY finished_at DESC LIMIT 1 FORMAT PrettyCompact"
```

---

## 📊 Этап 6: Валидация данных и бизнес-логики

### 6.1 Проверка целостности данных

```bash
# Проверка дедупликации
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT event_id, count() as cnt FROM zakaz.stg_qtickets_api_orders_raw GROUP BY event_id HAVING cnt > 1 ORDER BY cnt DESC LIMIT 10"

# Проверка агрегации
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT sales_date, sum(tickets_sold) as total_tickets, sum(revenue) as total_revenue FROM zakaz.fact_qtickets_sales_daily GROUP BY sales_date ORDER BY sales_date DESC LIMIT 7"

# Проверка view definitions
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT * FROM zakaz.v_qtickets_sales_dashboard LIMIT 5"
```

### 6.2 Проверка бизнес-метрик

```bash
# Проверка временных диапазонов
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT min(sale_ts), max(sale_ts) FROM zakaz.stg_qtickets_api_orders_raw"

# Проверка географии данных
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT city, count(*) as cnt FROM zakaz.stg_qtickets_api_orders_raw GROUP BY city ORDER BY cnt DESC"

# Проверка типов событий
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT event_name, count(*) as cnt FROM zakaz.stg_qtickets_api_orders_raw GROUP BY event_name ORDER BY cnt DESC LIMIT 10"
```

---

## 📝 Этап 7: Финальная валидация

### 7.1 Полный цикл теста

```bash
# Очистка и полный bootstrap
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true

cd /tmp/zakaz_test/dashboard-mvp/infra/clickhouse
../../scripts/bootstrap_clickhouse.sh
../../scripts/bootstrap_datalens.sh

# Production запуск
cd ../..
docker build -f integrations/qtickets_api/Dockerfile -t qtickets_api:final .
docker run --rm \
  --network clickhouse_default \
  --env-file secrets/.env.qtickets_api \
  qtickets_api:final

# Проверка результатов
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT 'FINAL TEST' as test, status, count() as cnt FROM zakaz.meta_job_runs GROUP BY status"
```

### 7.2 Чек-лист готовности к передаче

- [ ] ClickHouse стартует с правильными ролями и грантами
- [ ] DataLens пользователь имеет HTTP доступ
- [ ] Qtickets API loader работает в production режиме
- [ ] Все таблицы созданы и содержат данные
- [ ] Юнит-тесты проходят
- [ ] CI pipeline выполняется успешно
- [ ] Валидация схемы проходит без ошибок
- [ ] Обработка ошибок работает корректно
- [ ] Бизнес-логика работает ожидаемо
- [ ] Логирование структурированное и информативное

---

## 🚨 Критерии отказа

Тест считается проваленным, если:
1. Любой из bootstrap скриптов завершается с ошибкой
2. Qtickets loader не может записать данные в ClickHouse
3. DataLens не может подключиться к ClickHouse
4. Юнит-тесты не проходят
5. CI pipeline не выполняется
6. Данные не соответствуют ожидаемой структуре
7. Обработка ошибок работает некорректно

---

## 📋 Отчет о тестировании

После завершения всех тестов необходимо создать отчет:

```
Дата тестирования: <YYYY-MM-DD>
Версия: <commit hash>
Окружение: <описание>

Результаты:
- ClickHouse RBAC: ✅/❌
- Qtickets API: ✅/❌
- DataLens доступ: ✅/❌
- Юнит-тесты: ✅/❌
- CI/CD: ✅/❌

Замечания:
<список проблем если есть>

Рекомендации:
<список рекомендаций>

Готовность к передаче: ✅/❌