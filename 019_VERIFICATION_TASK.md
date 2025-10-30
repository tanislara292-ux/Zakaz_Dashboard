# Задача 019: Верификация и исправление критических проблем для передачи проекта заказчику

**Дата:** 2025-10-30  
**Приоритет:** Критический  
**Исполнитель:** Кодер  
**Верификатор:** Архитектор  

---

## ФАЗА 1 — Ознакомиться (Input & Контекст)

### 1.1. Быстрый аудит репозитория

* Пролистать корень и каталоги:
  * `infra/clickhouse/` — конфигурация ClickHouse, RBAC, bootstrap скрипты
  * `integrations/qtickets_api/` — Qtickets API клиент и loader
  * `scripts/` — bootstrap и валидационные скрипты
  * `docs/` — документация, deployment playbook
  * `.github/workflows/` — CI/CD пайплайны

### 1.2. Ключевые документы (минимальный пакет для чтения)

1. `docs/DEPLOYMENT.md` — пошаговый deployment playbook
2. `docs/changelog/CHANGELOG-015.md` — изменения в текущей версии
3. `dashboard-mvp/README.md` — quickstart и архитектура
4. `infra/clickhouse/bootstrap_roles_grants.sql` — RBAC конфигурация
5. `integrations/qtickets_api/loader.py` — основной loader

### 1.3. Локальная проверка окружения

* Скопировать `infra/clickhouse/.env.example` → `infra/clickhouse/.env`
* Запустить bootstrap:
  ```bash
  cd dashboard-mvp/infra/clickhouse
  ../../scripts/bootstrap_clickhouse.sh
  ../../scripts/bootstrap_datalens.sh
  ```
* Критерий готовности к работе (DoR):
  * ClickHouse стартует с правильными ролями и грантами
  * DataLens пользователь имеет HTTP доступ
  * Qtickets API loader работает в dry-run режиме

---

## ФАЗА 2 — Спланировать (Декомпозиция и план выполнения)

### 2.1. Принятие задачи

* Сопоставить задачу с Артефактами:
  * **Критические проблемы:** отсутствуют файлы, упомянутые в документации
  * **Модули правок:** `scripts/`, `.github/workflows/`, `integrations/qtickets_api/`
  * **Влияние на заказчика:** невозможность развернуть и протестировать систему

### 2.2. Аналитическая записка (ADR)

```
# ADR-019: Исправление критических проблем для передачи проекта заказчику
Дата: 2025-10-30
Контекст: В ходе верификации обнаружены отсутствующие файлы, упомянутые в документации и changelog, что блокирует развертывание системы
Решение: Создать отсутствующие файлы и обеспечить полную функциональность системы
Контракты данных: без изменений
Риски: Отсутствие CI/CD, невозможность валидации схемы, неполная функциональность inventory
Тест-план: Локальное тестирование bootstrap, dry-run Qtickets, проверка CI
Критерии приёмки (DoD): 
- Все файлы из документации существуют и работают
- Bootstrap скрипты выполняются без ошибок
- Qtickets loader работает в production режиме
- CI pipeline выполняется успешно
```

### 2.3. План изменений (Issue/PR чек-лист)

* Создать ветку: `fix/019-missing-critical-files`
* Согласовать перечень файлов:
  * Код: `scripts/validate_clickhouse_schema.py`, `.github/workflows/ci.yml`
  * Документация: обновить ссылки в README.md при необходимости
  * Тесты: расширить покрытие для новых компонентов
* Определить артефакты проверки: логи bootstrap, скриншоты CI, результаты dry-run

---

## ФАЗА 3 — Реализовать (Код → Тесты → Документация → Отчёт → Коммиты)

### 3.1. Реализация

**Задача 1: Создать `scripts/validate_clickhouse_schema.py`**
* Функционал:
  - Валидация структуры таблиц ClickHouse
  - Проверка наличия всех REQUIRED_TABLES из bootstrap_clickhouse.sh
  - Валидация грантов и ролей
  - Проверка view definitions
* Интерфейс командной строки:
  ```bash
  python scripts/validate_clickhouse_schema.py [--host HOST] [--port PORT] [--user USER] [--password PASSWORD]
  ```

**Задача 2: Создать `.github/workflows/ci.yml`**
* Шаги:
  - Checkout кода
  - Setup Python с зависимостями
  - Запуск `scripts/validate_clickhouse_schema.py`
  - Запуск pytest для `integrations/qtickets_api/tests/`
  - Сборка Docker образа `integrations/qtickets_api/Dockerfile`
* Триггеры: push, pull_request

**Задача 3: Реализовать inventory функциональность в Qtickets API**
* В `integrations/qtickets_api/client.py`:
  - Реализовать `list_shows(event_id)` метод
  - Реализовать полный `fetch_inventory_snapshot()` метод
  - Добавить обработку пагинации и ошибок
* В `integrations/qtickets_api/inventory_agg.py`:
  - Использовать новые методы клиента
  - Добавить кэширование для оптимизации

### 3.2. Тестирование

* Юнит-тесты:
  ```bash
  pytest integrations/qtickets_api/tests/ -v
  ```
* Интеграционные:
  ```bash
  # Проверка валидатора схемы
  python scripts/validate_clickhouse_schema.py
  
  # Bootstrap тест
  cd infra/clickhouse && ../../scripts/bootstrap_clickhouse.sh
  
  # Qtickets dry-run
  ./scripts/smoke_qtickets_dryrun.sh --env-file secrets/.env.qtickets_api
  ```
* CI тест:
  - Запушить ветку и проверить выполнение GitHub Actions

### 3.3. Обновление документации

* `docs/changelog/CHANGELOG-015.md` — добавить дату завершения
* `README.md` — убедиться что все ссылки рабочие
* `docs/DEPLOYMENT.md` — добавить проверку CI в prerequisites

### 3.4. Итоговый отчёт

```
Задача: 019 - Исправление критических проблем для передачи проекта заказчику
Суть изменений:
- Создан отсутствующий скрипт валидации схемы ClickHouse
- Добавлен CI/CD pipeline для автоматического тестирования
- Реализована полная функциональность inventory в Qtickets API

Контракты данных:
- Изменения столбцов: нет
- Правила дедуп/нормализации: без изменений

Проверки:
- Юнит-тесты: все проходят
- Интеграционные: bootstrap успешен, dry-run работает
- Валидация схем: скрипт создан и работает
- CI pipeline: выполняется успешно

Риски и как мониторим:
- Отсутствие файлов: решено созданием
- CI/CD failures: мониторинг через GitHub Actions
- Inventory ошибки: логирование и retry логика

Результат:
- Все файлы из документации существуют и функциональны
- Система готова к передаче заказчику
- CI/CD pipeline обеспечивает качество кода
```

### 3.5. Коммиты и PR

* Формат commit messages:
  * `feat(ci): add GitHub Actions workflow for automated testing`
  * `feat(scripts): implement ClickHouse schema validation`
  * `feat(qtickets-api): implement inventory functionality`
* PR приложить:
  * ссылку на ADR-019,
  * скриншоты успешного CI,
  * логи bootstrap тестов,
  * результаты dry-run

---

## Критерии приёмки (DoD)

- [ ] `scripts/validate_clickhouse_schema.py` создан и работает
- [ ] `.github/workflows/ci.yml` создан и выполняется успешно
- [ ] Qtickets API inventory функциональность реализована
- [ ] Bootstrap скрипты выполняются без ошибок
- [ ] Qtickets loader работает в production режиме
- [ ] Все тесты проходят
- [ ] Документация обновлена
- [ ] PR оформлен по чек-листу

---

## Риски и мониторинг

* **Риск:** Отсутствующие файлы блокируют развертывание
  * **Митигация:** Создать все недостающие файлы
* **Риск:** CI failures блокируют merges
  * **Митигация:** Локальное тестирование перед пушем
* **Риск:** Inventory ошибки в production
  * **Митигация:** Детальное логирование и retry логика

---

## TL;DR (короткая памятка)

1. **Создать:** `scripts/validate_clickhouse_schema.py` и `.github/workflows/ci.yml`
2. **Реализовать:** полную inventory функциональность в Qtickets API
3. **Протестировать:** bootstrap, dry-run, CI pipeline
4. **Задокументировать:** изменения в changelog и README
5. **Сдать:** работающую систему заказчику