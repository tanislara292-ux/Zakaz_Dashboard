# ADR-0002: DataLens ↔ ClickHouse подключение

Дата: 2025-10-11
Статус: Принято

## Контекст

После завершения EPIC-CH-01 с развёртыванием ClickHouse и базовой инфраструктуры, следующий шаг — обеспечить прямое подключение DataLens к ClickHouse для визуализации данных продаж. Текущий прототип использует Google Sheets как промежуточное звено, что создает задержки и ограничения в производительности.

Требуется обеспечить безопасный и производительный доступ DataLens к данным в ClickHouse, исключив Google Sheets из цепочки визуализации.

## Решение

### 1. Вариант доступа к ClickHouse

Выбран **Вариант B — HTTPS через реверс-прокси** как рекомендуемый:

1. **Добавлен Caddy** в `docker-compose.yml` в качестве реверс-прокси
2. **Настроен Caddyfile** для автоматического получения TLS-сертификата от Let's Encrypt
3. **Реализовано проксирование** запросов с `ch.your-domain:443` на `clickhouse:8123`

Альтернативные варианты задокументированы в RUNBOOK_DATALENS.md:
- Вариант A: Прямой HTTP 8123 с firewall-allowlist
- Вариант C: SSH-туннель/бастион (временный)

### 2. BI-слой в ClickHouse

Созданы представления для DataLens без дубликатов данных:

```sql
-- Основное представление с полными данными
CREATE OR REPLACE VIEW zakaz.v_sales_latest AS
SELECT
    report_date       AS sale_date,
    event_date,
    event_name,
    city,
    tickets_sold,
    revenue,
    refunds_amount,
    currency
FROM zakaz.stg_qtickets_sales FINAL;

-- Агрегированное представление за 14 дней для быстрых графиков
CREATE OR REPLACE VIEW zakaz.v_sales_14d AS
SELECT
    toDate(event_date) AS d,
    city,
    event_name,
    sum(tickets_sold) AS tickets_sold,
    sum(revenue)      AS revenue,
    sum(refunds_amount) AS refunds_amount
FROM zakaz.stg_qtickets_sales FINAL
WHERE report_date >= today() - 14
GROUP BY d, city, event_name;
```

### 3. Управление правами доступа

Настроены права для пользователя `datalens_reader`:

```sql
-- Текущие права: полный доступ на чтение
GRANT SELECT ON zakaz.* TO datalens_reader;

-- Опциональные ограниченные права (закомментированы)
-- REVOKE SELECT ON zakaz.* FROM datalens_reader;
-- GRANT SELECT ON zakaz.v_sales_latest TO datalens_reader;
-- GRANT SELECT ON zakaz.v_sales_14d TO datalens_reader;
-- GRANT SELECT ON zakaz.stg_qtickets_sales TO datalens_reader;
```

## Контракты данных

### v_sales_latest

| Поле | Тип | Описание |
|------|-----|----------|
| sale_date | Date | Дата формирования отчёта |
| event_date | Date | Дата мероприятия |
| event_name | String | Название мероприятия |
| city | String | Город |
| tickets_sold | UInt32 | Количество проданных билетов |
| revenue | Decimal(12,2) | Выручка |
| refunds_amount | Decimal(12,2) | Сумма возвратов |
| currency | FixedString(3) | Валюта |

### v_sales_14d

| Поле | Тип | Описание |
|------|-----|----------|
| d | Date | Дата мероприятия |
| city | String | Город |
| event_name | String | Название мероприятия |
| tickets_sold | UInt32 | Сумма проданных билетов |
| revenue | Decimal(12,2) | Сумма выручки |
| refunds_amount | Decimal(12,2) | Сумма возвратов |

## Риски

1. **Производительность запросов с FINAL** — использование `FINAL` в представлениях может снижать производительность при больших объёмах данных
   - **Митигация:** использование `v_sales_14d` для быстрых агрегаций; в будущем — замена на материализованные представления

2. **Проблемы с TLS-сертификатами** — автоматическое получение сертификатов от Let's Encrypt может потребовать настройки DNS
   - **Митигация:** подробная документация в RUNBOOK_DATALENS.md; альтернативные варианты доступа

3. **Ограничения прав доступа** — VIEW может требовать доступа к исходным таблицам
   - **Митигация:** предоставлены права на `stg_qtickets_sales` при необходимости

## Тест-план

1. **Проверка доступности ClickHouse через HTTPS:**
   ```bash
   curl -I https://ch.your-domain/?query=SELECT%201
   ```

2. **Проверка представлений:**
   ```sql
   SELECT count() FROM zakaz.v_sales_latest;
   SELECT count() FROM zakaz.v_sales_14d;
   ```

3. **Проверка прав доступа:**
   ```sql
   -- Подключение как datalens_reader
   SELECT count() FROM zakaz.v_sales_latest;
   ```

4. **Тестирование подключения в DataLens:**
   - Создание подключения `ch_zakaz_prod`
   - Создание источника `src_ch_sales_latest`
   - Создание датасета `ds_sales`
   - Создание дашборда `Zakaz — Sales (MVP)`

## Критерии приёмки (DoD)

- [ ] HTTPS-доступ к ClickHouse настроен через реверс-прокси
- [ ] Представления `v_sales_latest` и `v_sales_14d` созданы и работают
- [ ] Права доступа для `datalens_reader` настроены корректно
- [ ] Подключение в DataLens успешно создано и протестировано
- [ ] Датасет `Sales` создан на основе `v_sales_latest`
- [ ] MVP-дашборд с 3 виджетами создан и работает
- [ ] Документация RUNBOOK_DATALENS.md обновлена
- [ ] Скриншоты подключения и дашборда приложены

## Последствия

1. **Устранено** промежуточное звено Google Sheets в цепочке визуализации
2. **Улучшена** производительность загрузки данных в дашборды
3. **Обеспечена** безопасность передачи данных через HTTPS
4. **Создана** основа для дальнейшего развития BI-слоя в ClickHouse

## Будущие улучшения

1. **Материализованные представления** для замены `FINAL` и повышения производительности
2. **Оптимизация структуры** представлений под конкретные сценарии использования
3. **Настройка мониторинга** производительности запросов
4. **Интеграция с SSO** для управления доступом к DataLens