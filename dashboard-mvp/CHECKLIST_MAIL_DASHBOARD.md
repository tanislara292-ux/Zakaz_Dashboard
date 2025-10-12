# Чеклист развертывания почтового дашборда

## ✅ Подготовка инфраструктуры

- [ ] ClickHouse запущен и доступен
- [ ] Caddy настроен для HTTPS прокси
- [ ] Пользователи `etl_writer` и `datalens_reader` созданы

## ✅ DDL и таблицы

- [ ] Файл `infra/clickhouse/init_mail.sql` создан
- [ ] Таблицы созданы через `clickhouse-client --multiquery < init_mail.sql`
- [ ] Проверено: `SHOW TABLES FROM zakaz LIKE '%sales%'`

## ✅ Почтовый инжестор

- [ ] Директория `mail-python/` создана
- [ ] `requirements.txt` с зависимостями создан
- [ ] `gmail_ingest.py` с логикой инжестора создан
- [ ] `.env.sample` шаблон конфигурации создан
- [ ] Директория `secrets/gmail/` создана
- [ ] Виртуальное окружение Python создано: `python3 -m venv .venv`
- [ ] Зависимости установлены: `pip install -r requirements.txt`
- [ ] `.env` файл сконфигурирован

## ✅ Gmail API

- [ ] Проект в Google Cloud Console создан
- [ ] Gmail API включен
- [ ] OAuth 2.0 Client ID (Desktop) создан
- [ ] `credentials.json` скачан в `mail-python/secrets/gmail/`
- [ ] Тестовая авторизация пройдена: `python gmail_ingest.py --dry-run --limit 1`

## ✅ Автоматизация

- [ ] `gmail-ingest.service` скопирован в `/etc/systemd/system/`
- [ ] `gmail-ingest.timer` скопирован в `/etc/systemd/system/`
- [ ] Systemd перезагружен: `systemctl daemon-reload`
- [ ] Таймер включен: `systemctl enable --now gmail-ingest.timer`
- [ ] Статус проверен: `systemctl list-timers | grep gmail-ingest`

## ✅ DataLens

- [ ] Источник данных ClickHouse создан
- [ ] Подключение к `zakaz` базе настроено
- [ ] Датасет на основе `v_sales_combined` создан
- [ ] Тестовый запрос выполнен успешно
- [ ] Базовый дашборд создан

## 🔍 Проверка работоспособности

### ClickHouse
```bash
# Сырые данные
clickhouse-client -q "SELECT count() FROM zakaz.stg_mail_sales_raw"

# Последние данные
clickhouse-client -q "SELECT * FROM zakaz.v_sales_14d ORDER BY d DESC LIMIT 5"

# Объединенные данные
clickhouse-client -q "SELECT count() FROM zakaz.v_sales_combined WHERE event_date >= today() - 7"
```

### Systemd
```bash
# Статус сервиса
systemctl status gmail-ingest.timer

# Логи
journalctl -u gmail-ingest.service -n 20

# Активные таймеры
systemctl list-timers | grep gmail
```

### Python
```bash
cd mail-python
source .venv/bin/activate

# Тестовый запуск
python gmail_ingest.py --dry-run --limit 3

# Полный запуск
python gmail_ingest.py
```

## 🚨 Возможные проблемы и решения

### Нет данных из Gmail
- [ ] Проверить `credentials.json` существует и корректен
- [ ] Проверить `token.json` создан после авторизации
- [ ] Проверить `GMAIL_QUERY` в `.env`
- [ ] Запустить вручную с `--dry-run`

### Проблемы с ClickHouse
- [ ] Проверить подключение: `clickhouse-client --query "SELECT 1"`
- [ ] Проверить права: `SHOW GRANTS FOR etl_writer`
- [ ] Проверить существование таблиц: `SHOW TABLES FROM zakaz`

### Проблемы с DataLens
- [ ] Проверить права `datalens_reader`
- [ ] Проверить HTTPS прокси
- [ ] Проверить сетевую доступность

## 📊 Метрики успеха

- [ ] Инжестор запускается автоматически каждые 15 минут
- [ ] Данные из почты загружаются в ClickHouse
- [ ] Дедупликация работает (нет дублей в `v_sales_latest`)
- [ ] DataLens показывает актуальные данные
- [ ] Дашборд обновляется автоматически

## 🎯 Следующие шаги

1. Мониторинг freshness данных
2. Алерты при отсутствии данных
3. Расширение парсинга для других форматов
4. Оптимизация производительности
5. Добавление更多 источников данных

---

**Готовность к продакшену:** [ ] Да / [ ] Нет

**Дата проверки:** ___________

**Ответственный:** ___________