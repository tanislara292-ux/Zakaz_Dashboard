# VK Ads Integration

## Назначение

Интеграция с VK Ads API для загрузки статистики по рекламным кампаниям в ClickHouse.

## Структура

- `loader.py` - основной загрузчик данных
- `README.md` - документация

## Конфигурация

1. Скопируйте шаблон конфигурации:
   ```bash
   cp ../../configs/.env.vk.sample ../../secrets/.env.vk
   ```

2. Заполните реальные значения в `secrets/.env.vk`:
   ```
   VK_TOKEN=your_vk_ads_api_token_here
   VK_ACCOUNT_IDS=123456789,987654321
   VK_DAYS_BACK=30
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

# Загрузка данных для конкретных аккаунтов
python loader.py --accounts 123456789,987654321

# Использование другого файла конфигурации
python loader.py --env /path/to/.env.vk
```

### Использование как модуля

```python
from integrations.vk_ads.loader import VkAdsLoader, VkAdsClient
from integrations.common import get_client
from datetime import date

# Инициализация клиентов
ch_client = get_client('secrets/.env.vk')

with VkAdsClient(token='your_token') as api_client:
    # Создание загрузчика
    loader = VkAdsLoader(ch_client, api_client, [123456789, 987654321])
    
    # Загрузка данных
    rows_count = loader.load_statistics(
        date_from=date(2023, 10, 1), 
        date_to=date(2023, 10, 31)
    )
    print(f"Загружено строк: {rows_count}")
```

## Таблицы в ClickHouse

### Исходные данные

- `zakaz.fact_vk_ads_daily` - статистика по рекламным кампаниям

### Витрины

- `zakaz.v_marketing_daily` - сводная статистика по маркетингу
- `zakaz.v_campaign_performance` - эффективность рекламных кампаний

## Парсинг UTM-меток

Загрузчик автоматически парсит UTM-метки из URL объявлений и дополнительно обрабатывает `utm_content` формата `<city>_<dd>_<mm>`:

- `utm_city` - город из utm_content
- `utm_day` - день из utm_content
- `utm_month` - месяц из utm_content

## Метаданные

Информация о запусках задач записывается в таблицу `zakaz.meta_job_runs`.

## Логирование

Логи пишутся в:
- Консоль
- Файл `logs/vk_ads.log` (если настроен)

Уровень логирования и формат настраиваются через переменные окружения:
- `LOG_LEVEL` - уровень логирования (DEBUG, INFO, WARNING, ERROR)
- `LOG_JSON` - использовать JSON формат (true/false)
- `LOG_FILE` - путь к файлу логов

## Расписание

Рекомендуемое расписание для автоматического запуска:
- Ежедневно в 00:00 MSK для получения данных за предыдущий день

Пример systemd таймера:
```
[Unit]
Description=VK Ads Data Loader
After=network.target

[Service]
Type=oneshot
User=etl
WorkingDirectory=/opt/zakaz_dashboard
ExecStart=/usr/bin/python3 /opt/zakaz_dashboard/integrations/vk_ads/loader.py
Environment=PYTHONPATH=/opt/zakaz_dashboard
Restart=on-failure
RestartSec=30

[Timer]
OnCalendar=*-*-* 00:00:00
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
- Уникальному ключу `(stat_date, account_id, campaign_id, ad_group_id, ad_id)`

## Мониторинг

Для мониторинга работоспособности используйте:
- Таблицу `zakaz.meta_job_runs` для отслеживания запусков
- Вьюху `zakaz.v_data_freshness` для контроля свежести данных
- Smoke-проверки в `infra/clickhouse/smoke_checks_integrations.sql`

## Особенности

1. **Детализация по группам объявлений**: Загрузчик получает статистику с детализацией по ad_group_id
2. **Парсинг UTM**: Автоматическое извлечение UTM-меток из URL объявлений
3. **Чанковая загрузка**: Данные загружаются порциями по 200 ID для оптимизации запросов к API
4. **Поддержка нескольких аккаунтов**: Можно загружать данные для нескольких рекламных кабинетов