# VK Ads Pipeline

Python-сервис для выгрузки статистики рекламных кампаний VK Ads и записи агрегированных данных в Google Sheets (`VK_Ads`). Сервис закрывает часть EPIC B0–B3: обеспечивается регулярная синхронизация метрик с соблюдением схемы `schemas/sheets/vk_ads.yaml`.

## Возможности
- Авторизация по токену клиента или агентства.
- Загрузка структуры кампаний/объявлений (`ads.getCampaigns`, `ads.getAds`).
- Получение посуточной статистики (`ads.getStatistics`) по объявлениям.
- Парсинг UTM-меток из посадочных ссылок.
- Запись данных в Google Sheets с дедупликацией по ключу `date` + `campaign_id` + `adgroup_id`.
- CLI-скрипт `python -m vk_ads_pipeline.main` с логированием прогресса.

## Настройка окружения
1. Cкопируйте `.env.sample` на уровень репозитория в `.env` и заполните блок `VK_*`.
2. Убедитесь, что Google Service Account имеет права на таблицу `BI_Central`.
3. Установите зависимости:
   ```bash
   cd vk-python
   python -m venv .venv
   . .venv/bin/activate
   pip install -e ".[dev]"
   ```

## Запуск
```bash
python -m vk_ads_pipeline.main --date-from 2024-09-01 --date-to 2024-09-30
```

Параметры CLI дополняют значения из `.env`. При успешном запуске отчёт сохраняется в лист `VK_Ads`. Предусмотрены dry-run и выгрузка в CSV (см. `python -m vk_ads_pipeline.main --help`).

## Тестирование
```bash
pytest
```

Юнит-тесты покрывают разбор конфигурации, построение запросов и нормализацию статистики.
