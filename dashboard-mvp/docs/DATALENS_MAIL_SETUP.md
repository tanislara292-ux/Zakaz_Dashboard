# Настройка DataLens для почтового инжестора

## 1. Подключение к ClickHouse

1. Перейдите в DataLens → Источники данных → Добавить → ClickHouse
2. Настройте подключение:
   - **Хост**: `https://<your-proxy-domain>`
   - **Порт**: `443`
   - **TLS/HTTPS**: включено
   - **База данных**: `zakaz`
   - **Пользователь**: `datalens_reader`
   - **Пароль**: `<password>`
   - **Способ подключения**: HTTP интерфейс

3. Проверьте подключение кнопкой "Проверить соединение"

## 2. Проверка данных

Откройте SQL-консоль в DataLens и выполните:

```sql
-- Проверка наличия данных
SELECT count() FROM zakaz.stg_mail_sales_raw;

-- Последние данные за 14 дней
SELECT * FROM zakaz.v_sales_14d ORDER BY d DESC LIMIT 10;

-- Проверка объединенных данных
SELECT * FROM zakaz.v_sales_combined ORDER BY event_date DESC LIMIT 5;
```

## 3. Создание датасета

1. Создайте новый датасет на основе таблицы `zakaz.v_sales_combined`
2. Настройте поля:

| Поле | Тип | Описание |
|------|-----|----------|
| event_date | Дата | Дата события |
| city | Строка | Город |
| event_name | Строка | Название события |
| tickets_sold | Число | Продано билетов |
| revenue | Число | Выручка |
| refunds | Число | Возвраты |
| net_revenue | Число | Чистая выручка |
| currency | Строка | Валюта |

3. Создайте вычисляемое поле `net_revenue = revenue - refunds` (если еще не существует)

## 4. Визуализации

### 4.1 График продаж по дням

- **Тип**: Линейный график
- **X**: `event_date`
- **Y**: `net_revenue`
- **Фильтр**: `event_date` >= сегодня() - 30 дней
- **Группировка**: по дням

### 4.2 Таблица топ-городов

- **Тип**: Таблица
- **Столбцы**: `city`, `tickets_sold`, `net_revenue`
- **Сортировка**: по `net_revenue` по убыванию
- **Фильтр**: последние 30 дней

### 4.3 Сравнение почты и QTickets

- **Тип**: Линейный график с двумя сериями
- **X**: `event_date`
- **Y1**: Сумма `tickets_sold` из `v_sales_latest` (почта)
- **Y2**: Сумма `tickets_sold` из `stg_qtickets_sales` (QTickets)
- **Фильтр**: последние 30 дней

## 5. Дашборд

Создайте дашборд со следующими виджетами:

1. **KPI виджеты**:
   - Общая выручка за период
   - Всего билетов продано
   - Средний чек
   - Топ-5 городов

2. **Графики**:
   - Динамика продаж по дням
   - Продажи по городам (столбчатая диаграмма)
   - Сравнение источников данных

3. **Фильтры**:
   - Период дат
   - Выбор города
   - Выбор источника данных

## 6. Обновление данных

DataLens автоматически обновляет данные при запросе к ClickHouse. 
Для проверки свежести данных используйте поле `_ingested_at` или создайте виджет с запросом:

```sql
SELECT 
  max(_ingested_at) as last_update,
  dateDiff('minute', max(_ingested_at), now()) as minutes_ago
FROM zakaz.stg_mail_sales_raw;
```

## 7. Диагностика проблем

### Нет данных в дашборде

1. Проверьте работу инжестора:
   ```sql
   SELECT count() FROM zakaz.stg_mail_sales_raw;
   ```

2. Проверьте последние загрузки:
   ```sql
   SELECT * FROM zakaz.stg_mail_sales_raw 
   ORDER BY _ingested_at DESC LIMIT 5;
   ```

3. Проверьте права доступа:
   ```sql
   SHOW GRANTS FOR datalens_reader;
   ```

### Некорректные данные

1. Проверьте хэши для отладки:
   ```sql
   SELECT row_hash, event_name, city, tickets_sold, revenue
   FROM zakaz.stg_mail_sales_raw
   WHERE event_date >= today() - 7
   ORDER BY _ingested_at DESC;
   ```

2. Проверьте дедупликацию:
   ```sql
   SELECT 
     event_date, 
     city, 
     event_name,
     count() as duplicates
   FROM zakaz.stg_mail_sales_raw
   WHERE event_date >= today() - 7
   GROUP BY event_date, city, event_name
   HAVING duplicates > 1;