# Архив компонентов Google Sheets

Этот каталог содержит компоненты, связанные с Google Sheets, которые были декоммиссированы в рамках EPIC-CH-07.

## Перемещенные компоненты

### appscript/
- **qtickets_api_ingest.gs** - Apps Script для загрузки данных из QTickets API в Google Sheets
- **README.md** - документация по Apps Script

### schemas/sheets/
- **logs.yaml** - схема листа Logs
- **plans.yaml** - схема листа Plans
- **qtickets.yaml** - схема листа QTickets
- **ref_utm.yaml** - схема листа Ref_UTM
- **vk_ads.yaml** - схема листа VK_Ads

### tools/
- **sheets_init.py** - скрипт инициализации структуры Google Sheets
- **sheets_validate.py** - скрипт валидации данных в Google Sheets

## Статус

Все эти компоненты были декоммиссированы 2025-10-11 в рамках перехода на архитектуру без Google Sheets. Данные теперь загружаются напрямую в ClickHouse через CDC-пайплайны.

## Восстановление

В случае необходимости восстановления функциональности Google Sheets:
1. Скопировать компоненты из этого каталога в исходные расположения
2. Настроить переменные окружения для Google Sheets API
3. Создать и настроить Google Spreadsheet
4. Восстановить триггеры в Google Apps Script

## Примечания

- Все данные из Google Sheets были перенесены в ClickHouse
- Текущая архитектура использует только ClickHouse как хранилище данных
- DataLens подключен напрямую к ClickHouse через HTTPS