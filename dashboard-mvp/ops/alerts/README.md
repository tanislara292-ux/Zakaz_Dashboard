# Мониторинг и Алертинг

## Назначение

Система мониторинга состояния интеграций и отправки уведомлений о проблемах.

## Структура

- `notify.py` - основной скрипт проверки и отправки уведомлений
- `README.md` - документация
- `../systemd/alerts.service` - systemd сервис для проверки
- `../systemd/alerts.timer` - systemd таймер для проверки
- `../healthcheck_integrations.py` - HTTP healthcheck сервер

## Компоненты

### 1. Система уведомлений (`notify.py`)

Автоматическая проверка:
- Неудачные запуски задач за последние 24 часа
- Свежесть данных (отставание более 2 дней)
- Общее здоровье системы

### 2. Healthcheck сервер (`healthcheck_integrations.py`)

HTTP эндпоинты для мониторинга:
- `/healthz` - базовая проверка
- `/healthz/detailed` - детальная проверка
- `/healthz/freshness` - проверка свежести данных

## Конфигурация

1. Скопируйте шаблон конфигурации:
   ```bash
   cp ../../configs/.env.alerts.sample ../../secrets/.env.alerts
   ```

2. Заполните реальные значения в `secrets/.env.alerts`:
   ```
   SMTP_HOST=smtp.yandex.ru
   SMTP_PORT=587
   SMTP_USER=your_email@yandex.ru
   SMTP_PASSWORD=your_app_password_here
   SMTP_USE_TLS=true
   ALERT_EMAIL_TO=ads-irsshow@yandex.ru,admin@example.com
   ```

## Установка и настройка

### 1. Установка systemd таймеров

```bash
# Перейти в директорию с таймерами
cd ../../ops/systemd

# Установить таймер алертов
sudo ./manage_timers.sh install

# Включить таймер алертов (проверка каждые 2 часа)
sudo ./manage_timers.sh enable alerts

# Включить healthcheck сервер
sudo systemctl enable healthcheck.service
sudo systemctl start healthcheck.service
```

### 2. Проверка работы

```bash
# Проверить статус таймеров
./manage_timers.sh status

# Проверить логи алертов
./manage_timers.sh logs alerts

# Проверить healthcheck сервер
curl http://localhost:8080/healthz
```

## Использование

### Запуск проверок вручную

```bash
# Проверка ошибок
python3 notify.py --check-errors

# Проверка свежести данных
python3 notify.py --check-freshness

# Полная проверка здоровья
python3 notify.py --check-health

# Проверка за последние 12 часов
python3 notify.py --check-errors --hours 12
```

### Healthcheck эндпоинты

```bash
# Базовая проверка
curl http://localhost:8080/healthz

# Детальная проверка
curl http://localhost:8080/healthz/detailed

# Проверка свежести данных
curl http://localhost:8080/healthz/freshness
```

Пример ответа `/healthz`:
```json
{
  "status": "ok",
  "timestamp": "2023-10-12T10:00:00+03:00",
  "checks": {
    "clickhouse": "ok"
  }
}
```

Пример ответа `/healthz/detailed`:
```json
{
  "status": "warning",
  "timestamp": "2023-10-12T10:00:00+03:00",
  "checks": {
    "clickhouse": {
      "status": "ok",
      "message": "ClickHouse connection"
    },
    "data_freshness": {
      "vk_ads": {
        "status": "warning",
        "latest_date": "2023-10-10",
        "days_behind": 2
      }
    },
    "job_runs": {
      "qtickets_loader": {
        "status": "ok",
        "last_run": "2023-10-12T09:45:00",
        "last_status": "success"
      }
    }
  }
}
```

## Типы алертов

### 1. Алерты об ошибках

Отправляются при обнаружении неудачных запусков задач:
- Статус: `error`
- Тема: 🚨 Ошибки в загрузчиках данных (N)
- Содержание: список задач с ошибками
- Периодичность: каждые 2 часа

### 2. Алерты о свежести данных

Отправляются при обнаружении устаревших данных:
- Статус: `warning`
- Тема: ⚠️ Устаревшие данные (N источников)
- Содержание: список источников с отставанием
- Периодичность: каждые 2 часа

### 3. Алерты о здоровье системы

Отправляются при проблемах с общей работоспособностью:
- Статус: `error` или `warning`
- Тема: 🏥 Проблемы со здоровьем системы
- Содержание: описание проблемы
- Периодичность: каждые 2 часа

## Метаданные алертов

Все алерты сохраняются в таблицу `zakaz.alerts`:

```sql
-- Просмотр последних алертов
SELECT * FROM zakaz.alerts
ORDER BY created_at DESC
LIMIT 10;

-- Статистика по алертам
SELECT 
    alert_type,
    count() as alerts_count,
    max(created_at) as last_alert
FROM zakaz.alerts
WHERE created_at >= today() - 7
GROUP BY alert_type
ORDER BY alerts_count DESC;
```

## Интеграция с внешними системами

### 1. Prometheus/Grafana

Можно настроить экспорт метрик через healthcheck:

```yaml
# Prometheus конфигурация
scrape_configs:
  - job_name: 'zakaz_integrations'
    metrics_path: '/healthz'
    static_configs:
      - targets: ['localhost:8080']
```

### 2. Uptime мониторинг

Настройте проверку эндпоинта:
- URL: `http://your-server:8080/healthz`
- Метод: GET
- Ожидаемый код: 200
- Проверка каждые 5 минут

### 3. Slack/Telegram интеграция

Для интеграции с мессенджерами можно использовать вебхуки:

```python
# Пример для Slack
def send_slack_notification(webhook_url, message):
    import requests
    payload = {"text": message}
    requests.post(webhook_url, json=payload)
```

## Диагностика проблем

### 1. Проверка логов

```bash
# Логи алертов
./manage_timers.sh logs alerts

# Логи healthcheck сервера
sudo journalctl -u healthcheck.service -f

# Логи конкретного загрузчика
./manage_timers.sh logs qtickets
```

### 2. Ручная проверка

```bash
# Проверка состояния загрузчиков
./manage_timers.sh status

# Проверка свежести данных в ClickHouse
curl "http://localhost:8080/healthz/freshness" | jq .

# Проверка неудачных запусков
python3 notify.py --check-errors --hours 24
```

### 3. Расширенная диагностика

```sql
-- Анализ неудачных запусков
SELECT 
    job,
    status,
    count() as runs,
    max(started_at) as last_run,
    groupArray(message) as errors
FROM zakaz.meta_job_runs
WHERE started_at >= today() - 7
  AND status = 'error'
GROUP BY job, status
ORDER BY runs DESC;

-- Анализ производительности
SELECT 
    job,
    avg(JSONExtractInt(metrics, 'duration')) as avg_duration,
    max(JSONExtractInt(metrics, 'duration')) as max_duration,
    avg(rows_processed) as avg_rows
FROM zakaz.meta_job_runs
WHERE started_at >= today() - 7
  AND status = 'success'
GROUP BY job
ORDER BY avg_duration DESC;
```

## Настройка оповещений

### 1. Email через Gmail

1. Включите 2FA в Gmail
2. Создайте пароль приложения:
   - Настройки → Безопасность → Пароли приложений
   - Создайте новый пароль для "Zakaz Alerts"
3. Используйте эти настройки:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   ```

### 2. Email через Yandex

1. Используйте эти настройки:
   ```
   SMTP_HOST=smtp.yandex.ru
   SMTP_PORT=587
   SMTP_USER=your_email@yandex.ru
   SMTP_PASSWORD=your_app_password
   ```

### 3. Множественные получатели

Укажите несколько email через запятую:
```
ALERT_EMAIL_TO=admin@example.com,dev@example.com,alerts@example.com
```

## Расписание проверок

| Проверка | Расписание | Описание |
|----------|------------|-----------|
| Ошибки задач | Каждые 2 часа | Проверка неудачных запусков за 24 часа |
| Свежесть данных | Каждые 2 часа | Проверка отставания данных |
| Healthcheck | Непрерывно | HTTP сервер для внешних проверок |
| Алерты | При обнаружении проблем | Email уведомления |

## Тестирование

```bash
# Тестирование отправки email
python3 -c "
from ops.alerts.notify import EmailNotifier
notifier = EmailNotifier('smtp.yandex.ru', 587, 'user@yandex.ru', 'password')
notifier.send_email(['test@example.com'], 'Test', 'Test message')
"

# Тестирование healthcheck
curl -v http://localhost:8080/healthz

# Тестирование алертов
python3 notify.py --check-errors --hours 1
```

## Устранение неполадок

### Проблема: Не приходят email уведомления

1. Проверьте настройки SMTP:
   ```bash
   python3 notify.py --check-errors 2>&1 | grep -i smtp
   ```

2. Проверьте логи systemd:
   ```bash
   ./manage_timers.sh logs alerts
   ```

3. Проверьте доступность SMTP сервера:
   ```bash
   telnet smtp.yandex.ru 587
   ```

### Проблема: Healthcheck недоступен

1. Проверьте статус сервиса:
   ```bash
   sudo systemctl status healthcheck.service
   ```

2. Проверьте порт:
   ```bash
   netstat -tlnp | grep 8080
   ```

3. Проверьте логи:
   ```bash
   sudo journalctl -u healthcheck.service -n 50
   ```

### Проблема: Ложные срабатывания алертов

1. Проверьте часовой пояс:
   ```sql
   SELECT now(), now() - INTERVAL 1 HOUR;
   ```

2. Проверьте последние запуски:
   ```sql
   SELECT * FROM zakaz.meta_job_runs
   ORDER BY started_at DESC
   LIMIT 10;