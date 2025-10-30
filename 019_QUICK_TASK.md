# КРАТКАЯ ЗАДАЧА ДЛЯ КОДЕРА - Исправление критических проблем

## 🎯 Цель
Создать отсутствующие файлы и реализовать функциональность для передачи проекта заказчику.

## 📁 Что нужно сделать (3 файла):

### 1. Создать `scripts/validate_clickhouse_schema.py`
**Что делать:** Скрипт для валидации схемы ClickHouse
**Откуда взять идеи:**
- Посмотреть `REQUIRED_TABLES` в `scripts/bootstrap_clickhouse.sh` (строки 101-109)
- Изучить структуру `bootstrap_roles_grants.sql`
- Использовать паттерны из `integrations/common/ch.py`

**Функционал:**
- Проверить наличие всех таблиц из REQUIRED_TABLES
- Валидировать права пользователей (admin, etl_writer, datalens_reader, backup_user)
- Проверить view definitions

### 2. Создать `.github/workflows/ci.yml`
**Что делать:** GitHub Actions для автоматического тестирования
**Откуда взять идеи:**
- Посмотреть существующий `.github/workflows/etl_dispatch.yml` для структуры
- Изучить шаги в `docs/DEPLOYMENT.md` (раздел Testing & CI)
- Использовать паттерны из CHANGELOG-015.md

**Шаги:**
- Checkout кода
- Setup Python с зависимостями из `integrations/qtickets_api/requirements.txt`
- Запуск `scripts/validate_clickhouse_schema.py`
- Запуск `pytest integrations/qtickets_api/tests/`
- Сборка Docker образа `integrations/qtickets_api/Dockerfile`

### 3. Реализовать inventory в `integrations/qtickets_api/client.py`
**Что делать:** Заменить заглушки на реальную функциональность
**Откуда взять идеи:**
- Изучить существующие методы `list_events()` и `fetch_orders_get()`
- Посмотреть `inventory_agg.py` для понимания структуры данных
- Использовать паттерны retry и error handling из существующего кода

**Методы для реализации:**
- `list_shows(event_id)` - получить shows для события
- `fetch_inventory_snapshot()` - полный снапшот inventory
- Использовать `get_seats(show_id)` который уже реализован

## 🧪 Как тестировать:

```bash
# 1. Bootstrap ClickHouse
cd dashboard-mvp/infra/clickhouse
../../scripts/bootstrap_clickhouse.sh

# 2. Проверить валидатор
python scripts/validate_clickhouse_schema.py

# 3. Запустить тесты
pytest integrations/qtickets_api/tests/ -v

# 4. Собрать Docker образ
docker build -f integrations/qtickets_api/Dockerfile -t test .

# 5. Проверить Qtickets loader
./scripts/smoke_qtickets_dryrun.sh --env-file secrets/.env.qtickets_api
```

## ✅ Критерии готовности:
- Все 3 файла созданы и работают
- Bootstrap выполняется без ошибок
- Тесты проходят
- Docker образ собирается
- Qtickets loader работает в dry-run режиме

## 📋 Порядок работы:
1. Создать ветку `fix/019-missing-critical-files`
2. Реализовать `scripts/validate_clickhouse_schema.py`
3. Создать `.github/workflows/ci.yml`
4. Реализовать inventory методы в `client.py`
5. Протестировать всё вместе
6. Сделать PR с описанием изменений

**Готово! После этого система готова к передаче заказчику.**