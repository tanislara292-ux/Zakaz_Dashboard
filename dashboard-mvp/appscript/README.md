# QTickets API Ingest (Apps Script)

1. Открой таблицу BI_Central → Расширения → Apps Script → создай проект.
2. Вставь код из `qtickets_api_ingest.gs`.
3. В `CFG` укажи `SPREADSHEET_ID` и нужные параметры (при необходимости скорректируй `LOOKBACK_DAYS`).
4. В Script Properties добавь `QTICKETS_API_TOKEN` и, при необходимости, `ALERT_EMAILS` (через запятую).
5. Убедись, что листы `QTickets`, `Inventory`, `Logs` существуют (скрипт создаст при первом запуске).
6. Запусти `createDailyTrigger()` — получишь запуск каждый день в 00:00.
7. Выполни `qticketsSync()` вручную, чтобы выдать доступы и проверить работу.
