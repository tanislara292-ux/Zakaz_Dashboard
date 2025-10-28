# ADR-003: Исправление ClickHouse схемы для v_qtickets_freshness

**Дата:** 2025-10-28

**Контекст:**
При повторном bootstrap на сервере возникает ошибка:
`Code: 47. DB::Exception: Unknown expression or function identifier 'start_date' …`

Причина — представление `zakaz.v_qtickets_freshness` обращается к полям `start_date`/`end_date`,
которые не созданы в `zakaz.dim_events` в используемом SQL-файле.

**Решение:**
1. Унифицировать определение таблицы `dim_events` во всех SQL файлах
2. Обновить представление `v_qtickets_freshness` для использования корректных полей
3. Убрать дублирующиеся определения таблиц
4. Обеспечить совместимость с существующими скриптами

**Контракты данных:**
- `dim_events` будет содержать поля: `start_date`, `end_date` (Nullable(Date))
- `fact_qtickets_inventory` будет содержать поля: `_loaded_at` (DateTime)
- `v_qtickets_freshness` будет использовать `start_date` из `dim_events`

**Риски:**
- Возможное нарушение обратной совместимости с существующими ETL скриптами
- Необходимость обновления зависимых представлений
- Потеря данных при пересоздании таблиц

**Тест-план:**
- Двойной прогон bootstrap скрипта на чистом ClickHouse
- Smoke-тест Qtickets
- Запуск pytest в vk-python
- Валидация схемы через `scripts/validate_clickhouse_schema.py`

**Критерии приёмки (DoD):**
- Bootstrap проходит без ошибок дважды подряд
- Все представления ссылаются на существующие поля
- Smoke-тесты Qtickets и VK проходят успешно
- CI пайплайн выполняется без ошибок