# Systemd Таймеры Интеграций

## Назначение

Автоматический запуск загрузчиков данных по расписанию с помощью systemd таймеров.

## Структура

- `*.service` - файлы сервисов systemd
- `*.timer` - файлы таймеров systemd
- `manage_timers.sh` - скрипт для управления таймерами
- `README.md` - документация

## Список таймеров

| Таймер | Расписание | Назначение | Статус |
|--------|------------|------------|--------|
| qtickets | Каждые 15 минут | Загрузка данных QTickets API | Включен |
| vk_ads | Ежедневно в 00:00 MSK | Загрузка статистики VK Ads | Включен |
| direct | Ежедневно в 00:10 MSK | Загрузка статистики Яндекс.Директ | Включен |
| gmail_ingest | Каждые 4 часа | Резервный канал Gmail | Отключен |
| alerts | Каждые 2 часа | Проверка ошибок и алертинг | Включен |

## Установка и настройка

### 1. Копирование файлов таймеров

```bash
# Сделать скрипт управления исполняемым
chmod +x manage_timers.sh

# Установить все таймеры в systemd (требует прав root)
sudo ./manage_timers.sh install
```

### 2. Включение таймеров

```bash
# Включить все основные таймеры
sudo ./manage_timers.sh enable qtickets
sudo ./manage_timers.sh enable vk_ads
sudo ./manage_timers.sh enable direct
sudo ./manage_timers.sh enable alerts

# Gmail таймер отключен по умолчанию (резервный канал)
# sudo ./manage_timers.sh enable gmail

# Включить healthcheck сервер
sudo systemctl enable healthcheck.service
sudo systemctl start healthcheck.service
```

### 3. Проверка статуса

```bash
# Показать статус всех таймеров
./manage_timers.sh status

# Показать статус конкретного таймера
./manage_timers.sh status qtickets
```

## Управление таймерами

### Основные команды

```bash
# Показать справку
./manage_timers.sh help

# Показать расписание всех таймеров
./manage_timers.sh schedule

# Показать логи таймера
./manage_timers.sh logs qtickets

# Включить/отключить таймер
sudo ./manage_timers.sh enable qtickets
sudo ./manage_timers.sh disable qtickets

# Запустить/остановить/перезапустить таймер
sudo ./manage_timers.sh start qtickets
sudo ./manage_timers.sh stop qtickets
sudo ./manage_timers.sh restart qtickets
```

### Прямое управление через systemctl

```bash
# Статус таймера
systemctl status qtickets.timer

# Включение таймера
sudo systemctl enable qtickets.timer
sudo systemctl start qtickets.timer

# Отключение таймера
sudo systemctl stop qtickets.timer
sudo systemctl disable qtickets.timer

# Просмотр логов
journalctl -u qtickets.service -f
```

## Расписание таймеров

### QTickets
- **Расписание**: `*:0/15` (каждые 15 минут)
- **Задержка**: до 60 секунд (случайная)
- **Назначение**: Регулярная загрузка данных о продажах и мероприятиях

### VK Ads
- **Расписание**: `*-*-* 00:00:00` (ежедневно в полночь)
- **Задержка**: до 5 минут (случайная)
- **Назначение**: Загрузка статистики за предыдущий день

### Яндекс.Директ
- **Расписание**: `*-*-* 00:10:00` (ежедневно в 00:10)
- **Задержка**: до 5 минут (случайная)
- **Назначение**: Загрузка статистики за предыдущий день

### Gmail (резервный канал)
- **Расписание**: `*-*-* 0,4,8,12,16,20:00:00` (каждые 4 часа)
- **Задержка**: до 5 минут (случайная)
- **Назначение**: Резервный канал при недоступности QTickets API
- **Статус**: Отключен по умолчанию

### Alerts
- **Расписание**: `*-*-* */2:00:00` (каждые 2 часа)
- **Задержка**: до 5 минут (случайная)
- **Назначение**: Проверка ошибок и отправка уведомлений
- **Статус**: Включен

### Healthcheck
- **Тип**: Сервис (непрерывная работа)
- **Порт**: 8080
- **Назначение**: HTTP эндпоинты для мониторинга
- **Статус**: Включен

## Логирование

### Журналы systemd

Все логи пишутся в systemd journal:

```bash
# Просмотр логов конкретного сервиса
journalctl -u qtickets.service -n 100

# Отслеживание логов в реальном времени
journalctl -u qtickets.service -f

# Просмотр логов всех таймеров
journalctl -u "*timer" --since "1 hour ago"
```

### Файловые логи

Дополнительно логи пишутся в файлы (если настроено в переменных окружения):

- `logs/qtickets.log`
- `logs/vk_ads.log`
- `logs/direct.log`
- `logs/gmail.log`

## Мониторинг

### Проверка статуса

```bash
# Проверить активные таймеры
systemctl list-timers

# Проверить статус всех сервисов
systemctl status qtickets.service vk_ads.service direct.service
```

### Метаданные в ClickHouse

Информация о запусках записывается в таблицу `zakaz.meta_job_runs`:

```sql
-- Последние запуски
SELECT * FROM zakaz.meta_job_runs
ORDER BY started_at DESC
LIMIT 10;

-- Статистика по задачам
SELECT
    job,
    status,
    count() as runs,
    max(started_at) as last_run
FROM zakaz.meta_job_runs
GROUP BY job, status
ORDER BY job, status;
```

### Алерты

Информация об алертах сохраняется в таблицу `zakaz.alerts`:

```sql
-- Последние алерты
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

### Healthcheck эндпоинты

HTTP сервер предоставляет следующие эндпоинты:
- `GET /healthz` - базовая проверка здоровья
- `GET /healthz/detailed` - детальная проверка с метриками
- `GET /healthz/freshness` - проверка свежести данных

```bash
# Проверка здоровья
curl http://localhost:8080/healthz

# Детальная проверка
curl http://localhost:8080/healthz/detailed

# Проверка свежести данных
curl http://localhost:8080/healthz/freshness
```

```sql
-- Последние запуски
SELECT * FROM zakaz.meta_job_runs 
ORDER BY started_at DESC 
LIMIT 10;

-- Статистика по задачам
SELECT 
    job,
    status,
    count() as runs,
    max(started_at) as last_run
FROM zakaz.meta_job_runs
GROUP BY job, status
ORDER BY job, status;
```

## Обработка ошибок

### Автоматический перезапуск

Все сервисы настроены на автоматический перезапуск при ошибках:
- `Restart=on-failure`
- `RestartSec=30` (задержка 30 секунд)

### Уведомления об ошибках

При ошибках запуска:
1. Записывается в `zakaz.meta_job_runs` со статусом 'error'
2. Логируется в systemd journal
3. Можно настроить уведомления через `ops/alerts/notify.py`

### Таймауты

Настроены таймауты для предотвращения зависания:
- QTickets: 300 секунд (5 минут)
- VK Ads: 600 секунд (10 минут)
- Direct: 600 секунд (10 минут)
- Gmail: 300 секунд (5 минут)

## Обслуживание

### Ручной запуск

```bash
# Запустить сервис вручную
sudo systemctl start qtickets.service

# Запустить с параметрами
sudo systemctl start qtickets.service
```

### Отключение на время обслуживания

```bash
# Отключить все таймеры
sudo ./manage_timers.sh disable qtickets
sudo ./manage_timers.sh disable vk_ads
sudo ./manage_timers.sh disable direct

# Или остановить без отключения
sudo ./manage_timers.sh stop qtickets
sudo ./manage_timers.sh stop vk_ads
sudo ./manage_timers.sh stop direct
```

### Проверка после обслуживания

```bash
# Проверить статус
./manage_timers.sh status

# Запустить вручную для проверки
sudo ./manage_timers.sh start qtickets

# Просмотреть логи
./manage_timers.sh logs qtickets
```

## Безопасность

### Права доступа

- Сервисы запускаются от пользователя `etl`
- Переменные окружения загружаются из защищенных файлов в `secrets/`
- Логи не содержат конфиденциальной информации

### Изоляция

- Рабочая директория: `/opt/zakaz_dashboard`
- Переменная `PYTHONPATH` ограничена директорией проекта
- Ограниченные права пользователя `etl`

## Резервное копирование конфигурации

```bash
# Создать бэкап файлов systemd
sudo cp -r /etc/systemd/system/*timer* /backup/systemd/
sudo cp -r /etc/systemd/system/*service* /backup/systemd/

# Восстановление из бэкапа
sudo cp /backup/systemd/*timer* /etc/systemd/system/
sudo cp /backup/systemd/*service* /etc/systemd/system/
sudo systemctl daemon-reload