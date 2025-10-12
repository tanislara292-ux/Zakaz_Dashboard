# Gmail Integration

## Назначение

Резервный канал для загрузки данных о продажах из писем Gmail в ClickHouse. Используется как fallback при недоступности QTickets API.

## Структура

- `loader.py` - основной инжестор данных
- `README.md` - документация

## Конфигурация

1. Скопируйте шаблон конфигурации:
   ```bash
   cp ../../configs/.env.gmail.sample ../../secrets/.env.gmail
   ```

2. Заполните реальные значения в `secrets/.env.gmail`:
   ```
   GMAIL_CREDENTIALS_PATH=secrets/gmail/credentials.json
   GMAIL_TOKEN_PATH=secrets/gmail/token.json
   GMAIL_QUERY=subject:QTickets OR subject:qTickets OR from:qtickets.ru
   GMAIL_DAYS_BACK=7
   ```

3. Настройте OAuth2 доступ к Gmail:
   - Создайте проект в Google Cloud Console
   - Включите Gmail API
   - Создайте учетные данные OAuth2
   - Скачайте `credentials.json` в `secrets/gmail/`

## Использование

### Запуск из командной строки

```bash
# Загрузка писем за последние 7 дней (по умолчанию)
python loader.py

# Загрузка писем за последние 3 дня
python loader.py --days 3

# Использование кастомного поискового запроса
python loader.py --query "subject:Продажи newer_than:5d"

# Ограничение количества сообщений
python loader.py --limit 50

# Тестовый запуск без загрузки данных
python loader.py --dry-run

# Использование другого файла конфигурации
python loader.py --env /path/to/.env.gmail
```

### Использование как модуля

```python
from integrations.gmail.loader import GmailLoader, GmailClient
from integrations.common import get_client

# Инициализация клиентов
ch_client = get_client('secrets/.env.gmail')
gmail_client = GmailClient('secrets/gmail/credentials.json', 'secrets/gmail/token.json')
gmail_client.authenticate()

# Создание загрузчика
loader = GmailLoader(ch_client, gmail_client)

# Загрузка данных
rows_count = loader.load_messages('subject:QTickets newer_than:7d')
print(f"Загружено строк: {rows_count}")
```

## Таблицы в ClickHouse

### Исходные данные

- `zakaz.stg_qtickets_sales_raw` - сырые данные о продажах из писем

### Витрины

- `zakaz.v_sales_latest` - актуальные данные о продажах без дублей
- `zakaz.v_sales_14d` - продажи за последние 14 дней

## Обработка данных

Инжестор извлекает данные из:

1. **HTML таблиц** в теле письма
2. **CSV вложений** с различными кодировками (UTF-8, CP1251)
3. **Различных форматов дат** (YYYY-MM-DD, DD.MM.YY, DD/MM/YYYY)
4. **Различных форматов чисел** (с запятой или точкой как десятичный разделитель)

### Нормализация полей

Поддерживаются следующие названия колонок (рус/англ):

| Целевое поле | Варианты названий |
|--------------|-------------------|
| date | date, дата, event_date, дата события |
| event_id | event_id, ид события, идентификатор |
| event_name | event, событие, название события |
| city | city, город |
| tickets_sold | tickets_sold, продано билетов, билетов |
| revenue | revenue, выручка, сумма, сумма продажи |
| refunds | refunds, возвраты, refund |
| currency | currency, валюта |

## Метаданные

Информация о запусках задач записывается в таблицу `zakaz.meta_job_runs`.

## Логирование

Логи пишутся в:
- Консоль
- Файл `logs/gmail.log` (если настроен)

Уровень логирования и формат настраиваются через переменные окружения:
- `LOG_LEVEL` - уровень логирования (DEBUG, INFO, WARNING, ERROR)
- `LOG_JSON` - использовать JSON формат (true/false)
- `LOG_FILE` - путь к файлу логов

## Расписание

**ВНИМАНИЕ**: Gmail инжестор отключен по умолчанию и используется только как резервный канал.

Если необходимо включить, рекомендуется расписание:
- Каждые 4 часа для проверки новых писем

Пример systemd таймера:
```ini
[Unit]
Description=Gmail Data Ingestor
After=network.target

[Service]
Type=oneshot
User=etl
WorkingDirectory=/opt/zakaz_dashboard
ExecStart=/usr/bin/python3 /opt/zakaz_dashboard/integrations/gmail/loader.py
Environment=PYTHONPATH=/opt/zakaz_dashboard
Restart=on-failure
RestartSec=30

[Timer]
OnCalendar=*-*-* 0,4,8,12,16,20:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Для включения таймера:
```bash
sudo systemctl enable gmail-ingest.timer
sudo systemctl start gmail-ingest.timer
```

## Обработка ошибок

При ошибках:
1. Логируется подробное сообщение об ошибке
2. Записывается информация о неудачном запуске в `zakaz.meta_job_runs`
3. Процесс завершается с кодом 1
4. Ошибки обработки отдельных сообщений не прерывают весь процесс

## Идемпотентность

Инжестор идемпотентен - повторные запуски не создают дубликаты данных благодаря:
- Использованию `ReplacingMergeTree` с `_ver` для удаления старых версий
- Уникальному ключу `(event_date, city, event_name)` в витрине `v_sales_latest`
- Хешированию строк для дедупликации

## Мониторинг

Для мониторинга работоспособности используйте:
- Таблицу `zakaz.meta_job_runs` для отслеживания запусков
- Вьюху `zakaz.v_data_freshness` для контроля свежести данных
- Smoke-проверки в `infra/clickhouse/smoke_checks_integrations.sql`

## Особенности

1. **Резервный канал**: Используется только при недоступности основного API
2. **Гибкость обработки**: Поддерживает различные форматы данных и кодировки
3. **Безопасность**: Использует OAuth2 для доступа к Gmail
4. **Отключен по умолчанию**: Требуется явное включение при необходимости

## Поисковые запросы

Примеры полезных поисковых запросов:

```bash
# Поиск писем от QTickets
"from:qtickets.ru newer_than:7d"

# Поиск по темам
"subject:QTickets OR subject:qTickets newer_than:7d"

# Поиск с вложениями
"has:attachment subject:Продажи newer_than:7d"

# Комбинированный запрос
"from:qtickets.ru OR subject:Продажи newer_than:7d"
```

## Ограничения API

Gmail API имеет следующие ограничения:
- Квота на количество запросов в день
- Ограничение на размер сообщений
- Требуется OAuth2 аутентификация

При превышении лимитов инжестор автоматически повторяет запрос с экспоненциальным бэкоффом.