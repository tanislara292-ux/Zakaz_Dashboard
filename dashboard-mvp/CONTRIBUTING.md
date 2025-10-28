# Чеклист разработчика Zakaz Dashboard

## Перед коммитом

### 1. Проверка ClickHouse DDL
Если вы изменили SQL файлы в `infra/clickhouse/`:
```bash
python3 dashboard-mvp/scripts/validate_clickhouse_schema.py
```

### 2. Проверка синтаксиса Python
```bash
python3 -m compileall dashboard-mvp
```

### 3. Тестирование VK Ads (если изменяли vk-python)
```bash
cd dashboard-mvp/vk-python
pip install -e ".[dev]"
python3 -m pytest -v
```

### 4. Локальный bootstrap ClickHouse (если изменяли DDL)
```bash
# Очистка
cd dashboard-mvp/infra/clickhouse
docker compose down -v

# Первый запуск
bash ../../scripts/bootstrap_clickhouse.sh

# Проверка идемпотентности
bash ../../scripts/bootstrap_clickhouse.sh
```

### 5. Smoke test для Qtickets (опционально)
```bash
bash dashboard-mvp/scripts/smoke_qtickets_dryrun.sh
```

## CI Pipeline

GitHub Actions автоматически выполняет следующие проверки:

1. **validate-schema** - Валидация ClickHouse DDL
2. **compile-python** - Компиляция всего Python кода
3. **test-vk-python** - Pytest для vk-python
4. **build-qtickets** - Docker build для QTickets API
5. **smoke-test** - Полный smoke тест (только на push в main)

## Стандарты кода

### SQL (ClickHouse DDL)
- Используйте `CREATE TABLE IF NOT EXISTS`
- Все таблицы должны иметь версию (`_ver`) для ReplacingMergeTree
- Партиционирование должно быть детерминированным (избегайте `rand()`)
- Проверяйте отсутствие дублирующих `CREATE TABLE` для одной таблицы

### Python
- Код должен проходить `python3 -m compileall`
- Все модули с тестами должны иметь 100% покрытие критичных функций
- Используйте type hints где возможно

### Docker
- Образы должны собираться без предупреждений
- Используйте multi-stage builds для оптимизации размера
- Указывайте точные версии базовых образов

## Структура коммитов

Используйте conventional commits:

```
feat(clickhouse): добавление новой таблицы для событий
fix(qtickets): исправление дублирования данных
docs(readme): обновление инструкций по запуску
chore(ci): добавление smoke тестов в pipeline
```

## Troubleshooting

### Bootstrap fails on второй запуск
- Проверьте отсутствие дублирующих CREATE TABLE
- Убедитесь, что VIEW используют правильные колонки из текущей схемы

### Docker build fails
- Проверьте наличие Dockerfile и requirements.txt
- Убедитесь, что все пути относительно PROJECT_ROOT

### Pytest fails
- Установите dev зависимости: `pip install -e ".[dev]"`
- Проверьте pythonpath в pyproject.toml

## Полезные команды

```bash
# Проверить все таблицы в ClickHouse
docker exec -i ch-zakaz clickhouse-client --user=admin --password=admin_pass -q "SHOW TABLES FROM zakaz"

# Просмотреть структуру таблицы
docker exec -i ch-zakaz clickhouse-client --user=admin --password=admin_pass -q "DESCRIBE zakaz.dim_events"

# Запустить все проверки локально
python3 dashboard-mvp/scripts/validate_clickhouse_schema.py
python3 -m compileall dashboard-mvp
cd dashboard-mvp/vk-python && python3 -m pytest -v
```
