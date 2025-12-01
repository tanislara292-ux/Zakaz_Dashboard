# QTickets Integration

## Назначение

Интеграция с QTickets API для загрузки данных о мероприятиях, продажах и инвентаре в ClickHouse.

## Структура

- `loader.py` - основной загрузчик данных
- `README.md` - документация

## Конфигурация

1. Скопируйте шаблон конфигурации:
   ```bash
   cp ../../configs/.env.qtickets.sample ../../secrets/.env.qtickets
   ```

2. Заполните реальные значения в `secrets/.env.qtickets`:
   ```
   QTICKETS_TOKEN=your_qtickets_api_token_here
   QTICKETS_DAYS_BACK=30
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
python loader.py --env /path/to/.env.qtickets
```

### Использование как модуля

```python
from integrations.qtickets.loader import QTicketsLoader, QTicketsAPIClient
from integrations.common import get_client
from datetime import date

# Инициализация клиентов
ch_client = get_client('secrets/.env.qtickets')
api_client = QTicketsAPIClient(token='your_token')

# Создание загрузчика
loader = QTicketsLoader(ch_client, api_client)

# Загрузка данных
results = loader.load_all(date_from=date(2023, 10, 1), date_to=date(2023, 10, 31))
print(results)
```

## Таблицы в ClickHouse

### Исходные данные

- `zakaz.stg_qtickets_sales_raw` - сырые данные о продажах
- `zakaz.dim_events` - справочник мероприятий

### Витрины

- `zakaz.v_sales_latest` - актуальные данные о продажах без дублей
- `zakaz.v_sales_14d` - продажи за последние 14 дней

## Метаданные

Информация о запусках задач записывается в таблицу `zakaz.meta_job_runs`.

## Логирование

Логи пишутся в:
- Консоль
- Файл `logs/qtickets.log` (если настроен)

Уровень логирования и формат настраиваются через переменные окружения:
- `LOG_LEVEL` - уровень логирования (DEBUG, INFO, WARNING, ERROR)
- `LOG_JSON` - использовать JSON формат (true/false)
- `LOG_FILE` - путь к файлу логов

## Расписание

Рекомендуемое расписание для автоматического запуска:
- Каждые 30 минут для получения свежих данных

Пример systemd таймера:
```
[Unit]
Description=QTickets Data Loader
After=network.target

[Service]
Type=oneshot
User=etl
WorkingDirectory=/opt/zakaz_dashboard
ExecStart=/usr/bin/python3 /opt/zakaz_dashboard/integrations/qtickets/loader.py
Environment=PYTHONPATH=/opt/zakaz_dashboard
Restart=on-failure
RestartSec=30

[Timer]
OnCalendar=*:0/30
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
- Использованию VIEW `v_sales_latest` для получения актуальных данных без дублей

## Мониторинг

Для мониторинга работоспособности используйте:
- Таблицу `zakaz.meta_job_runs` для отслеживания запусков
- Вьюху `zakaz.v_data_freshness` для контроля свежести данных
- Smoke-проверки в `infra/clickhouse/smoke_checks_integrations.sql`