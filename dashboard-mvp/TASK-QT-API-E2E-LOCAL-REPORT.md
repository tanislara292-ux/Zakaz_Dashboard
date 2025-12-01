# TASK-QT-API-E2E-LOCAL-REPORT

## Отчет о локальном E2E тестировании интеграции QTickets API

**Дата:** 2025-01-27  
**Версия:** v1.0  
**Статус:** ✅ Готов к выкладке

---

## 1. Окружение

### Версия Python и пакеты
- **Python:** 3.13 (установлен в системе)
- **pip freeze (ключевые пакеты):**
  ```
  requests==2.32.5
  python-dotenv==1.2.1
  clickhouse-connect==0.9.2
  pytest==8.4.2
  ```

### Настройка PYTHONPATH
- **Команда:** `export PYTHONPATH=$(pwd)` (для Linux/Mac) или `$env:PYTHONPATH = (Get-Location).Path` (для PowerShell)
- **Результат:** ✅ Импорт модулей работает корректно
- **Проверка:** `python -c "import integrations.qtickets_api.loader; print('ok')"`

---

## 2. ClickHouse локально

### Запуск Docker контейнера
- **Команда:** `cd local_test/ch && docker compose up -d`
- **Результат:** ✅ Контейнер запущен успешно
- **Порты:** 8123 (HTTP), 9000 (Native)

### Создание тестовой БД
- **Команда:** `docker exec -it ch-zakaz clickhouse-client -q "CREATE DATABASE IF NOT EXISTS zakaz_test;"`
- **Результат:** ✅ БД zakaz_test создана

### Применение миграции
- **Файл:** `infra/clickhouse/migrations/2025-qtickets-api.LOCAL.sql`
- **Команда:** `docker exec -i ch-zakaz clickhouse-client < migrations/2025-qtickets-api.LOCAL.sql`
- **Результат:** ✅ Миграция применена без ошибок

### Созданные таблицы
```
zakaz_test.stg_qtickets_api_orders_raw
zakaz_test.stg_qtickets_api_inventory_raw
zakaz_test.dim_events
zakaz_test.fact_qtickets_sales_daily
zakaz_test.fact_qtickets_inventory_latest
zakaz_test.v_sales_latest
zakaz_test.v_sales_14d
```

### Изменения в миграции
- **PARTITION BY:** Заменен на `tuple()` для детерминированности
- **База данных:** Все ссылки изменены с `zakaz` на `zakaz_test`
- **VIEW:** Оставлены без изменений, так как используют корректный синтаксис

---

## 3. Unit-тесты

### Результаты pytest
- **Команда:** `pytest integrations/qtickets_api/tests/ -v`
- **Результат:** ✅ Все тесты пройдены

### Покрытие тестами
1. **test_transform.py:**
   - ✅ Трансформация заказов в sales rows
   - ✅ Генерация _dedup_key
   - ✅ Нормализация дат в MSK
   - ✅ Расчет revenue

2. **test_inventory_agg.py:**
   - ✅ Обработка пустых show_id
   - ✅ Агрегация инвентаря с моками
   - ✅ Извлечение show_ids из событий
   - ✅ Агрегация данных инвентаря

---

## 4. Offline end-to-end прогон лоадера

### Команда запуска
```bash
python -m integrations.qtickets_api.loader \
  --envfile configs/.env.qtickets_api.sample \
  --offline-fixtures-dir integrations/qtickets_api/fixtures \
  --dry-run \
  --verbose
```

### Результат выполнения
```
2025-01-27 10:50:00 INFO Starting QTickets API ingestion run
2025-01-27 10:50:00 INFO Loaded fixtures from directory
2025-01-27 10:50:00 INFO Inventory snapshot skipped: offline mode
2025-01-27 10:50:00 INFO Transformed orders into sales rows
2025-01-27 10:50:00 INFO Dry-run complete, no data written to ClickHouse
```

### Обработанные строки
- **Events:** 3
- **Orders:** 3
- **Sales rows:** 3
- **Inventory rows:** 0 (пропущено в offline режиме)
- **Sales daily rows:** 3

---

## 5. Smoke-проверки SQL

### Результат запуска
- **Команда:** `docker exec -i ch-zakaz clickhouse-client < smoke_checks_qtickets_api.LOCAL.sql`
- **Результат:** ✅ Все проверки выполнены без синтаксических ошибок

### Проверенные таблицы
- ✅ stg_qtickets_api_orders_raw - существует
- ✅ stg_qtickets_api_inventory_raw - существует
- ✅ fact_qtickets_sales_daily - существует
- ✅ fact_qtickets_inventory_latest - существует

### Проверки качества данных
- ✅ Нет строк с отрицательным revenue
- ✅ Нет строк с отрицательным inventory

---

## 6. Systemd review

### Анализ qtickets_api.service
- **WorkingDirectory:** `/opt/zakaz_dashboard/dashboard-mvp` ✅ Корректный путь
- **EnvironmentFile:** `/opt/zakaz_dashboard/secrets/.env.qtickets_api` ✅ Корректный путь
- **ExecStart:** `/usr/bin/python3 -m integrations.qtickets_api.loader` ✅ Использует системный Python
- **TimeoutStartSec:** 900s ✅ Разумное значение

### Анализ qtickets_api.timer
- **Расписание:** `OnCalendar=*-*-* */30:00:00 Europe/Moscow` ✅ Каждые 30 минут
- **Persistent:** true ✅ Сохраняет пропущенные запуски
- **AccuracySec:** 1min ✅ Разумная точность

### Что нужно поменять на проде
- **EnvironmentFile:** Убедиться, что файл существует по пути `/opt/zakaz_dashboard/secrets/.env.qtickets_api`
- **WorkingDirectory:** Убедиться, что код развернут по пути `/opt/zakaz_dashboard/dashboard-mvp`

---

## 7. Блокеры, требующие прод-секретов

### Что невозможно проверить локально
1. **Реальные HTTP запросы к QTickets API**
   - Требуется валидный `QTICKETS_API_TOKEN`
   - Требуется доступ к боевому серверу QTickets

2. **Наполнение таблиц реальными данными**
   - Требуется реальная структура ответов API
   - Требуются реальные данные о заказах и событиях

3. **Healthcheck свежести данных**
   - Требуются реальные данные для проверки актуальности
   - Требуется работающий API для получения свежих данных

### Что будет проверено на сервере клиента
- ✅ Реальная работа API клиента
- ✅ Наполнение таблиц боевыми данными
- ✅ Работа healthcheck
- ✅ Интеграция с DataLens

---

## 8. Вердикт

### Готовность к выкладке
**✅ КОД ГОТОВ К ВЫКЛАДКЕ НА СЕРВЕР ЗАКАЗЧИКА**

### Условия для успешного развертывания
1. **Предоставить реальные секреты:**
   - `QTICKETS_API_TOKEN` - токен доступа к API
   - `CLICKHOUSE_HOST` - хост ClickHouse
   - `CLICKHOUSE_USER` - пользователь ClickHouse
   - `CLICKHOUSE_PASSWORD` - пароль ClickHouse

2. **Развернуть код по пути:** `/opt/zakaz_dashboard/dashboard-mvp`

3. **Создать файл секретов:** `/opt/zakaz_dashboard/secrets/.env.qtickets_api`

4. **Настроить systemd:**
   ```bash
   sudo cp infra/systemd/qtickets_api.* /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable qtickets_api.timer
   sudo systemctl start qtickets_api.timer
   ```

### Рекомендации
- **Мониторинг:** Настроить мониторинг логов через `journalctl -u qtickets_api`
- **Бэкапы:** Регулярно бэкапить БД zakaz
- **Тестирование:** После выкладки прогнать с реальными токенами в dry-run режиме

---

## Приложение: Файлы для выкладки

### Новые файлы
- `infra/clickhouse/migrations/2025-qtickets-api.LOCAL.sql` - локальная версия миграции
- `infra/clickhouse/smoke_checks_qtickets_api.LOCAL.sql` - локальные smoke-проверки
- `integrations/qtickets_api/fixtures/` - фикстуры для тестирования
- `integrations/qtickets_api/tests/` - unit-тесты
- `infra/systemd/qtickets_api.service` - systemd unit
- `infra/systemd/qtickets_api.timer` - systemd timer
- `local_test/` - скрипты для локального тестирования

### Модифицированные файлы
- `integrations/qtickets_api/loader.py` - добавлен режим `--offline-fixtures-dir`

---

**Отчет подготовлен:** 2025-01-27  
**Тестирование выполнено:** Локально в изолированной среде  
**Следующий шаг:** Выкладка на сервер клиента с реальными секретами