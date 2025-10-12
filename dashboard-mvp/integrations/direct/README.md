# Яндекс.Директ Integration

## Назначение

Интеграция с Яндекс.Директ API для загрузки статистики по рекламным кампаниям в ClickHouse.

## Структура

- `loader.py` - основной загрузчик данных
- `README.md` - документация

## Конфигурация

1. Скопируйте шаблон конфигурации:
   ```bash
   cp ../../configs/.env.direct.sample ../../secrets/.env.direct
   ```

2. Заполните реальные значения в `secrets/.env.direct`:
   ```
   DIRECT_LOGIN=your_yandex_direct_login
   DIRECT_TOKEN=your_yandex_direct_api_token_here
   DIRECT_CLIENT_ID=your_client_id_here
   DIRECT_DAYS_BACK=30
   ```

## Использование

### Запуск из командной строки

```bash
# Загрузка данных за последние 30 дней (по умолчанию)
python loader.py

# Загрузка данных за последние 7 дней
python loader.py --days 7

# Загрузка данных за конкретный период
python loader.py --since 2023-10-01 --to 2023-10-31

# Использование другого файла конфигурации
python loader.py --env /path/to/.env.direct
```

### Использование как модуля

```python
from integrations.direct.loader import DirectLoader, DirectAPIClient
from integrations.common import get_client
from datetime import date

# Инициализация клиентов
ch_client = get_client('secrets/.env.direct')
api_client = DirectAPIClient(
    login='your_login',
    token='your_token',
    client_id='your_client_id'
)

# Создание загрузчика
loader = DirectLoader(ch_client, api_client)

# Загрузка данных
rows_count = loader.load_statistics(
    date_from=date(2023, 10, 1), 
    date_to=date(2023, 10, 31)
)
print(f"Загружено строк: {rows_count}")
```

## Таблицы в ClickHouse

### Исходные данные

- `zakaz.fact_direct_daily` - статистика по рекламным кампаниям

### Витрины

- `zakaz.v_marketing_daily` - сводная статистика по маркетингу
- `zakaz.v_campaign_performance` - эффективность рекламных кампаний

## Парсинг UTM-меток

Загрузчик автоматически парсит UTM-метки из отчета Яндекс.Директ и дополнительно обрабатывает `utm_content` формата `<city>_<dd>_<mm>`:

- `utm_city` - город из utm_content
- `utm_day` - день из utm_content
- `utm_month` - месяц из utm_content

## Метаданные

Информация о запусках задач записывается в таблицу `zakaz.meta_job_runs`.

## Логирование

Логи пишутся в:
- Консоль
- Файл `logs/direct.log` (если настроен)

Уровень логирования и формат настраиваются через переменные окружения:
- `LOG_LEVEL` - уровень логирования (DEBUG, INFO, WARNING, ERROR)
- `LOG_JSON` - использовать JSON формат (true/false)
- `LOG_FILE` - путь к файлу логов

## Расписание

Рекомендуемое расписание для автоматического запуска:
- Ежедневно в 00:10 MSK для получения данных за предыдущий день

Пример systemd таймера:
```
[Unit]
Description=Yandex.Direct Data Loader
After=network.target

[Service]
Type=oneshot
User=etl
WorkingDirectory=/opt/zakaz_dashboard
ExecStart=/usr/bin/python3 /opt/zakaz_dashboard/integrations/direct/loader.py
Environment=PYTHONPATH=/opt/zakaz_dashboard
Restart=on-failure
RestartSec=30

[Timer]
OnCalendar=*-*-* 00:10:00
Persistent=true

[Install]
WantedBy=timers.target
```

## Обработка ошибок

При ошибках:
1. Логируется подробное сообщение об ошибке
2. Записывается информация о неудачном запуске в `zakaz.meta_job_runs`
3. Процесс завершается с кодом 1

## Идемпотентность

Загрузчик идемпотентен - повторные запуски не создают дубликаты данных благодаря:
- Использованию `ReplacingMergeTree` с `_ver` для удаления старых версий
- Уникальному ключу `(stat_date, account_login, campaign_id, ad_group_id, ad_id)`

## Мониторинг

Для мониторинга работоспособности используйте:
- Таблицу `zakaz.meta_job_runs` для отслеживания запусков
- Вьюху `zakaz.v_data_freshness` для контроля свежести данных
- Smoke-проверки в `infra/clickhouse/smoke_checks_integrations.sql`

## Особенности

1. **Детализация по объявлениям**: Загрузчик получает статистику с детализацией по AdId
2. **Парсинг UTM**: Автоматическое извлечение UTM-меток из отчета Яндекс.Директ
3. **TSV формат отчетов**: Использует TSV формат для получения данных из API
4. **Фильтрация по статусу**: Загружает только активные и принятые кампании

## Ограничения API

Яндекс.Директ API имеет следующие ограничения:
- Максимальное количество строк в отчете - 10,000
- Ограничение на количество запросов в единицу времени
- Возможны задержки при формировании отчетов

При превышении лимитов загрузчик автоматически повторяет запрос с экспоненциальным бэкоффом.