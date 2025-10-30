# Задача 020: Финальное production тестирование Qtickets API

**Дата:** 2025-10-30  
**Исполнитель:** Кодер  
**Верификатор:** Архитектор  
**Приоритет:** Критический  

---

## 📋 КОНТЕКСТ ЗАДАЧИ

### Основная цель
Провести полное production тестирование Qtickets API интеграции на реальных API endpoints, чтобы убедиться в готовности системы к передаче заказчику.

### Критические требования
1. **Реальный Qtickets API токен** - должен быть получен и настроен
2. **Production окружение** - тестирование на реальном сервере заказчика
3. **Полная загрузка данных** - проверка загрузки заказов и инвентаря
4. **Валидация бизнес-логики** - проверка корректности данных
5. **Мониторинг ошибок** - проверка обработки ошибок
6. **DataLens интеграция** - проверка работы BI слоя

---

## 🔄 ПОСЛЕДОВАТЕЛЬНОСТЬ ДЕЙСТВИЙ КОДЕРА

### Этап 1: Подготовка production окружения

#### 1.1 Получение реальных учетных данных
- Связаться с ответственным лицом за production Qtickets API токен
- Получить доступ к production серверу заказчика
- Настроить `secrets/.env.qtickets_api` с реальными данными

#### 1.2 Настройка production окружения
```bash
# Копирование production конфигурации
cp configs/.env.qtickets_api.sample secrets/.env.qtickets_api.production

# Редактирование с реальными данными
vi secrets/.env.qtickets_api.production
```

**Обязательные переменные:**
- `QTICKETS_TOKEN` - реальный токен от Qtickets
- `QTICKETS_BASE_URL` - production URL Qtickets API
- `ORG_NAME` - название организации
- `CLICKHOUSE_HOST` - production ClickHouse хост
- `CLICKHOUSE_PORT` - production ClickHouse порт
- `CLICKHOUSE_DB` - имя базы данных
- `CLICKHOUSE_USER` - etl_writer пользователь
- `CLICKHOUSE_PASSWORD` - пароль etl_writer
- `DRY_RUN=false` - production режим

### Этап 2: Production тестирование Qtickets API

#### 2.1 Запуск production loader
```bash
# Сборка production образа
docker build -f integrations/qtickets_api/Dockerfile -t qtickets_api:production .

# Запуск в production режиме
docker run --rm \
  --network clickhouse_default \
  --env-file secrets/.env.qtickets_api.production \
  --name qtickets_production_test_$(date +%Y%m%d%H%M%S) \
  qtickets_api:production
```

#### 2.2 Проверка загрузки данных
```bash
# Проверка загруженных заказов
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_orders_raw WHERE _ver = (SELECT max(_ver) FROM zakaz.stg_qtickets_api_orders_raw)"

# Проверка загруженной инвентаризации (если реализовано)
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_inventory_raw WHERE _ver = (SELECT max(_ver) FROM zakaz.stg_qtickets_api_inventory_raw)"

# Проверка агрегированных данных
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count() FROM zakaz.fact_qtickets_sales_daily WHERE _ver = (SELECT max(_ver) FROM zakaz.fact_qtickets_sales_daily)"

docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count() FROM zakaz.fact_qtickets_inventory_latest WHERE _ver = (SELECT max(_ver) FROM zakaz.fact_qtickets_inventory_latest)"
```

#### 2.3 Проверка бизнес-логики
```bash
# Проверка временных диапазонов
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT min(sale_ts), max(sale_ts) FROM zakaz.stg_qtickets_api_orders_raw"

# Проверка географии данных
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT city, count(*) as cnt FROM zakaz.stg_qtickets_api_orders_raw GROUP BY city ORDER BY cnt DESC LIMIT 10"

# Проверка типов событий
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT event_name, count(*) as cnt FROM zakaz.stg_qtickets_api_orders_raw GROUP BY event_name ORDER BY cnt DESC LIMIT 10"
```

#### 2.4 Проверка обработки ошибок
```bash
# Проверка meta_job_runs
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT status, count(*) as cnt FROM zakaz.meta_job_runs WHERE job = 'qtickets_api' AND finished_at >= now() - INTERVAL 1 DAY GROUP BY status ORDER BY status"

# Проверка логов последнего запуска
docker logs $(docker ps -q --filter "name=qtickets_production_test" --format "{{.Names}}") | tail -50
```

### Этап 3: DataLens интеграция тестирование

#### 3.1 Проверка HTTP доступа
```bash
# Проверка DataLens доступа через HTTP
curl -s -u datalens_reader:ChangeMe123! \
  "http://production-clickhouse-host:8123/?query=SELECT+count()+FROM+zakaz.stg_qtickets_api_orders_raw"

# Проверка доступа к метаданным
curl -s -u datalens_reader:ChangeMe123! \
  "http://production-clickhouse-host:8123/?query=SELECT+count()+as+table_count+FROM+system.tables+WHERE+database=%3Dzakaz%27"
```

#### 3.2 Проверка view definitions
```bash
# Проверка работы view
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader --password=ChangeMe123! \
  -q "SELECT * FROM zakaz.v_qtickets_sales_dashboard LIMIT 5"

# Проверка агрегации
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader --password=ChangeMe123! \
  -q "SELECT sales_date, sum(tickets_sold) as total_tickets, sum(revenue) as total_revenue FROM zakaz.fact_qtickets_sales_daily GROUP BY sales_date ORDER BY sales_date DESC LIMIT 7"
```

### Этап 4: Стресс-тестирование

#### 4.1 Нагрузочное тестирование API
```bash
# Многократный запуск loader для проверки нагрузки
for i in {1..3}; do
  docker run --rm \
    --network clickhouse_default \
    --env-file secrets/.env.qtickets_api.production \
    --name qtickets_stress_test_${i}_$(date +%Y%m%d%H%M%S) \
    qtickets_api:production &
  sleep 30
done

# Ожидание завершения
wait

# Проверка результатов нагрузки
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT count(*) FROM zakaz.stg_qtickets_api_orders_raw GROUP BY _ver"
```

#### 4.2 Тестирование обработки ошибок
```bash
# Тест с неверным токеном
cp secrets/.env.qtickets_api.production secrets/.env.qtickets_api.bad
sed -i 's/QTICKETS_TOKEN=.*/QTICKETS_TOKEN=invalid_test_token/' secrets/.env.qtickets_api.bad

docker run --rm \
  --network clickhouse_default \
  --env-file secrets/.env.qtickets_api.bad \
  --name qtickets_error_test_$(date +%Y%m%d%H%M%S) \
  qtickets_api:production

# Проверка обработки ошибок
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT status, message FROM zakaz.meta_job_runs WHERE job = 'qtickets_api' ORDER BY finished_at DESC LIMIT 3"
```

### Этап 5: Валидация и мониторинг

#### 5.1 Схема валидация
```bash
# Запуск валидатора схемы
python scripts/validate_clickhouse_schema.py \
  --host production-clickhouse-host \
  --port 9000 \
  --user admin \
  --password admin_pass
```

#### 5.2 Производительность
```bash
# Проверка производительности запросов
docker exec ch-zakaz clickhouse-client \
  --user=admin --password=admin_pass \
  -q "SELECT query, count(), avg(duration) as avg_duration FROM system.query_log WHERE event_date >= now() - INTERVAL 1 HOUR AND query LIKE '%zakaz%' ORDER BY duration DESC LIMIT 10"
```

---

## 📊 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### Критерии успеха
1. ✅ Успешная загрузка данных из Qtickets API
2. ✅ Корректная обработка заказов и инвентаря
3. ✅ Правильная работа агрегации в fact таблицах
4. ✅ DataLens имеет полный доступ к данным
5. ✅ Обработка ошибок работает корректно
6. ✅ Система выдерживает нагрузочное тестирование
7. ✅ Schema validation проходит без ошибок

### Критерии отказа
1. ❌ Ошибки загрузки данных из Qtickets API
2. ❌ Некорректная обработка заказов
3. ❌ Проблемы с доступом DataLens
4. ❌ Ошибки в обработке ошибок
5. ❌ Система не выдерживает нагрузку
6. ❌ Schema validation не проходит

---

## 📝 ОТЧЕТ О ТЕСТИРОВАНИИ

### Формат отчета
```markdown
Дата тестирования: <YYYY-MM-DD>
Версия: <commit hash>
Окружение: <описание>
Выполнил: <имя исполнителя>

Результаты:
- Qtickets API загрузка: ✅/❌
- Обработка заказов: ✅/❌
- DataLens доступ: ✅/❌
- Нагрузочное тестирование: ✅/❌
- Schema validation: ✅/❌

Замечания:
<список проблем если есть>

Рекомендации:
<список рекомендаций>

Готовность к передаче: ✅/❌
```

---

## 🔧 ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ

### Инструменты
- Docker CLI
- ClickHouse client
- curl для HTTP тестов
- Python 3.11+ с зависимостями

### Мониторинг
- `zakaz.meta_job_runs` таблица
- `system.query_log` для производительности
- Docker логи контейнеров

---

## 📋 КОНТРОЛЬНЫЙ ЧЕК-ЛИСТ ПЕРЕД НАЧАЛОМ РАБОТЫ

- [ ] Получен реальный Qtickets API токен
- [ ] Настроено production окружение
- [ ] Выполнен запуск Qtickets API loader
- [ ] Проверена загрузка данных
- [ ] Проверена работа DataLens
- [ ] Выполнено нагрузочное тестирование
- [ ] Проведена schema validation
- [ ] Проверена обработка ошибок
- [ ] Создан отчет о тестировании
- [ ] Зафиксированы результаты
- [ ] Система готова к передаче заказчику

---

## 🚨 КРИТИЧЕСКИЕ ЗАМЕЧАНИЯ

1. **Безопасность:** Все тесты должны проводиться в production окружении
2. **Резервное копирование:** Перед тестированием создать backup данных
3. **Логирование:** Все действия должны быть задокументированы
4. **Время:** Выделить достаточное время на полное тестирование

---

**Подпись:**  
_Исполнитель:_ _Дата:_ _Верификатор:_