# ClickHouse Python Loader

Python-утилита для загрузки данных из Google Sheets в ClickHouse.

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Настройка

Установите переменные окружения в `.env`:

```bash
# Google Sheets
GOOGLE_SHEETS_SPREADSHEET_ID=<your_spreadsheet_id>
GOOGLE_SHEETS_QTICKETS_RANGE=QTickets!A:Z
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json

# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=<password>
CLICKHOUSE_DATABASE=zakaz
```

## Использование

### CLI интерфейс

```bash
# Базовый запуск (загрузка за последние 7 дней)
python cli.py --sheet-id $GOOGLE_SHEETS_SPREADSHEET_ID --days 7

# С указанием параметров ClickHouse
python cli.py \
  --sheet-id $GOOGLE_SHEETS_SPREADSHEET_ID \
  --range "QTickets!A:Z" \
  --days 7 \
  --ch-host localhost \
  --ch-port 8123 \
  --ch-user etl_writer \
  --ch-pass $CLICKHOUSE_ETL_WRITER_PASSWORD

# Подробное логирование
python cli.py --verbose --days 3
```

### Программное использование

```python
from loader.sheets_to_ch import SheetsToClickHouseLoader

loader = SheetsToClickHouseLoader()
loader.load_qtickets_to_clickhouse(days=7)
```

## Функциональность

### Обработка данных

- Нормализация строковых полей (`event_name`, `city`) → lower/strip
- Парсинг дат в различных форматах (YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY)
- Конвертация денежных сумм в `Decimal(12,2)`
- Формирование `dedup_key` для дедупликации
- Фильтрация пустых строк и некорректных данных

### Дедупликация

Используется стратегия на основе `ReplacingMergeTree` в ClickHouse:
- `dedup_key` формируется из ключевых полей
- `ingested_at` используется для определения последней версии
- Для консистентных выборок применяйте `FINAL` в запросах

### Батчевая загрузка

Данные загружаются батчами по умолчанию размером 1000 строк. Размер батча можно изменить через параметр `--batch-size`.

## Логирование

Логирование выполняется на уровне INFO с выводом:
- Общего количества обработанных строк
- Количество успешно вставленных строк
- Предупреждений о пропущенных/некорректных данных
- Ошибок подключения

## Тестирование

Для тестирования рекомендуется использовать тестовую таблицу или небольшой диапазон дат:

```bash
# Тестовый запуск за 1 день
python cli.py --days 1 --verbose
```

## Обработка ошибок

- Ошибки подключения к Google Sheets → прекращение выполнения
- Ошибки парсинга данных → пропуск строки с предупреждением
- Ошибки вставки в ClickHouse → прекращение выполнения
- Прерывание пользователем (Ctrl+C) → корректное завершение