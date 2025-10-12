# Аналитический дашборд Zakaz (MVP) + автоматизация VK Ads

Единый репозиторий артефактов проекта: документация, схемы данных, код интеграций и операционные шаблоны. Цель — за 10–14 дней собрать управляемый MVP отчётности в Yandex DataLens и подготовить полностью автоматизированную загрузку метрик VK Ads.

## Что реализовано
- Поток A2: Apps Script `qtickets_api_ingest.gs` синхронизирует заказы QTickets и остатки по мероприятиям в Google Sheets (`QTickets`, `Inventory`, `Logs`).
- Поток B0–B3: Python-сервис `vk-ads-pipeline` собирает посуточную статистику объявлений VK Ads, нормализует UTM-метки и записывает данные в лист `VK_Ads`.
- Инфраструктурные скрипты для выравнивания структуры таблиц (`tools/sheets_init.py`, `tools/sheets_validate.py`) по локальным схемам (`schemas/sheets/*.yaml`).
- Полный комплект проектной документации (`docs/`), включающий планы коммуникаций, scope, риски, DoR/DoD и архитектурную схему.

## Архитектура потоков
1. **QTickets → Google Sheets** — Apps Script выполняется по ежедневному триггеру, выгружает заказы и остатки, логирует статусы.
2. **VK Ads → Google Sheets** — Python-пайплайн по расписанию (cron / GitHub Actions) обращается к VK API, обогащает объявления UTM-метками, проводит дедупликацию и пишет данные в `VK_Ads`.
3. **Google Sheets → Yandex DataLens** — таблица `BI_Central` выступает staging-системой; DataLens читает данные через коннектор Google Sheets. Модели визуализации описаны в `docs/PROJECT_OVERVIEW.md`.

## Структура репозитория
```
├── appscript/             # Google Apps Script (поток QTickets)
├── docs/                  # Проектная документация и шаблоны
├── ops/                   # Операционные чек-листы и шаблоны писем
├── schemas/sheets/        # YAML-схемы листов Google Sheets
├── tools/                 # CLI-утилиты для Sheets и шаблоны проекта
└── vk-python/             # Python-сервис сбора статистики VK Ads
```

## Быстрый старт
1. Скопируйте `.env.sample` в `.env`, заполните доступы Google и параметры VK Ads.
2. Инициализируйте виртуальное окружение и pre-commit:
   ```bash
   bash tools/init.sh
   ```
3. Выравнивайте структуру таблиц по схемам:
   ```bash
   python tools/sheets_init.py
   ```
4. Проверьте данные на соответствие схемам:
   ```bash
   python tools/sheets_validate.py
   ```
5. Запустите пайплайн VK Ads:
   ```bash
   cd vk-python
   python -m vk_ads_pipeline.main --dry-run --verbose
   ```

## Документация
- `docs/PROJECT_OVERVIEW.md` — цели, KPI, артефакты и дорожная карта.
- `docs/COMMUNICATION_PLAN.md` — расписание созвонов, SLA и контакты.
- `docs/ACCESS_HANDBOOK.md` — порядок выдачи доступов и хранение секретов.
- `docs/RISK_LOG.md` — управление рисками и триггеры эскалации.
- `docs/ARCHITECTURE.md` — схема потоков данных и точки автоматизации.
- `ops/` — чек-листы кик-оффа, шаблоны писем, DoR/DoD.

## Тестирование и контроль качества
- Пиринг изменений через pre-commit (`black`, `markdownlint`, базовые проверки).
- `vk-python` содержит unit-тесты (`pytest`) на разбор конфигурации и нормализацию статистики.
- Логи исполнения пайплайнов доступны в листе `Logs`; критические ошибки дублируются на почту из Script Properties.

## Поддержка
Инструкции по коммуникациям и операционные контакты — в `docs/COMMUNICATION_PLAN.md`. Актуальные риски и эскалации — `docs/RISK_LOG.md`. Вопросы по инфраструктуре: smorozov@zakaz.example (техлид), bkoroleva@zakaz.example (проектный менеджер).
