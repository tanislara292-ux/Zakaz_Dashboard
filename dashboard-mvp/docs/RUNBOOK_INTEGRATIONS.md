# Runbook: Управление интеграциями

## Назначение

Руководство по управлению, мониторингу и устранению неполадок в системе интеграций Zakaz Dashboard.

## Обзор системы

### Компоненты

- **Источники данных**: QTickets API, VK Ads API, Яндекс.Директ API, Gmail API
- **Хранилище**: ClickHouse (таблицы stg_*, fact_*, dim_*, v_*)
- **Планировщик**: systemd таймеры
- **Мониторинг**: healthcheck сервер, алерты
- **Визуализация**: DataLens

### Расписание загрузок

| Таймер | Расписание | Источник | Назначение |
|--------|------------|----------|------------|
| qtickets | Каждые 15 минут | QTickets API | Продажи и мероприятия |
| vk_ads | Ежедневно 00:00 MSK | VK Ads API | Статистика рекламы |
| direct | Ежедневно 00:10 MSK | Яндекс.Директ API | Статистика рекламы |
| gmail_ingest | Каждые 4 часа | Gmail API | Резервный канал |
| alerts | Каждые 2 часа | - | Проверка ошибок |

## Ежедневные операции

### 1. Проверка состояния системы

```bash
# Проверить статус всех таймеров
cd /opt/zakaz_dashboard/ops/systemd
./manage_timers.sh status

# Проверить здоровье системы
curl http://localhost:8080/healthz/detailed | jq .

# Проверить свежесть данных
curl http://localhost:8080/healthz/freshness | jq .
```

### 2. Просмотр логов

```bash
# Логи за последние 24 часа
./manage_timers.sh logs qtickets
./manage_timers.sh logs vk_ads
./manage_timers.sh logs direct

# Логи алертов
./manage_timers.sh logs alerts

# Логи healthcheck сервера
sudo journalctl -u healthcheck.service -n 100
```

### 3. Анализ метаданных

```sql
-- Последние запуски задач
SELECT 
    job,
    status,
    started_at,
    finished_at,
    rows_processed,
    message
FROM zakaz.meta_job_runs
ORDER BY started_at DESC
LIMIT 20;

-- Статистика за последние 7 дней
SELECT 
    job,
    status,
    count() as runs,
    avg(rows_processed) as avg_rows,
    max(started_at) as last_run
FROM zakaz.meta_job_runs
WHERE started_at >= today() - 7
GROUP BY job, status
ORDER BY job, status;
```

## Устранение неполадок

### Проблема: QTickets загрузчик не работает

#### Симптомы
- Нет данных о продажах за последние часы
- Таймер qtickets показывает ошибки
- Алерты о неудачных запусках

#### Диагностика

```bash
# 1. Проверить статус таймера
./manage_timers.sh status qtickets

# 2. Просмотреть логи
./manage_timers.sh logs qtickets

# 3. Запустить вручную
cd /opt/zakaz_dashboard
python3 integrations/qtickets/loader.py --days 1

# 4. Проверить доступность API
curl -H "Authorization: Bearer $QTICKETS_TOKEN" \
     https://api.qtickets.ru/v1/events
```

#### Решения

1. **Проблемы с токеном**:
   ```bash
   # Обновить токен в secrets/.env.qtickets
   nano /opt/zakaz_dashboard/secrets/.env.qtickets
   # Перезапустить таймер
   sudo ./manage_timers.sh restart qtickets
   ```

2. **Проблемы с сетью**:
   ```bash
   # Проверить доступность API
   ping api.qtickets.ru
   telnet api.qtickets.ru 443
   ```

3. **Проблемы с данными**:
   ```sql
   -- Проверить наличие данных
   SELECT count() FROM zakaz.v_sales_latest 
   WHERE event_date >= today() - 1;
   
   -- Проверить на дубликаты
   SELECT count() FROM zakaz.v_sales_latest 
   GROUP BY event_date, city, event_name 
   HAVING count() > 1;
   ```

### Проблема: VK Ads загрузчик не работает

#### Симптомы
- Нет данных о рекламе за последние дни
- Таймер vk_ads показывает ошибки

#### Диагностика

```bash
# 1. Проверить статус таймера
./manage_timers.sh status vk_ads

# 2. Просмотреть логи
./manage_timers.sh logs vk_ads

# 3. Запустить вручную отладку
cd /opt/zakaz_dashboard
python3 integrations/vk_ads/loader.py --days 1

# 4. Проверить токен
curl -H "Authorization: Bearer $VK_TOKEN" \
     "https://api.vk.com/method/ads.getCampaigns?access_token=$VK_TOKEN&v=5.131"
```

#### Решения

1. **Недействительный токен**:
   - Обновить токен VK Ads
   - Проверить права доступа к рекламным кабинетам

2. **Проблемы с аккаунтами**:
   ```bash
   # Проверить ID аккаунтов
   echo $VK_ACCOUNT_IDS
   
   # Убедиться, что есть доступ к этим кабинетам
   ```

3. **Лимиты API**:
   - VK Ads имеет ограничения на количество запросов
   - Увеличить интервал между запросами в коде

### Проблема: Яндекс.Директ загрузчик не работает

#### Симптомы
- Нет данных о рекламе Яндекс.Директ
- Таймер direct показывает ошибки

#### Диагностика

```bash
# 1. Проверить статус таймера
./manage_timers.sh status direct

# 2. Просмотреть логи
./manage_timers.sh logs direct

# 3. Запустить вручную
cd /opt/zakaz_dashboard
python3 integrations/direct/loader.py --days 1
```

#### Решения

1. **Проблемы с аутентификацией**:
   - Обновить токен в secrets/.env.direct
   - Проверить права доступа к API

2. **Проблемы с отчетами**:
   - Яндекс.Директ API может задерживать создание отчетов
   - Увеличить таймауты в коде

### Проблема: Gmail загрузчик не работает

#### Симптомы
- Резервный канал не загружает данные
- Ошибки аутентификации OAuth2

#### Диагностика

```bash
# 1. Проверить статус таймера (если включен)
./manage_timers.sh status gmail

# 2. Запустить вручную с отладкой
cd /opt/zakaz_dashboard
python3 integrations/gmail/loader.py --dry-run --days 1

# 3. Проверить файлы OAuth2
ls -la /opt/zakaz_dashboard/secrets/gmail/
```

#### Решения

1. **Проблемы с OAuth2**:
   ```bash
   # Удалить старый токен
   rm /opt/zakaz_dashboard/secrets/gmail/token.json
   
   # Пересоздать авторизацию при следующем запуске
   python3 integrations/gmail/loader.py --dry-run
   ```

2. **Проблемы с доступом**:
   - Убедиться, что Gmail API включен в Google Cloud Console
   - Проверить права доступа для приложения

## Обслуживание

### Обновление конфигурации

```bash
# 1. Обновить переменные окружения
nano /opt/zakaz_dashboard/secrets/.env.qtickets
nano /opt/zakaz_dashboard/secrets/.env.vk
nano /opt/zakaz_dashboard/secrets/.env.direct

# 2. Перезапустить соответствующие таймеры
sudo ./manage_timers.sh restart qtickets
sudo ./manage_timers.sh restart vk_ads
sudo ./manage_timers.sh restart direct
```

### Обновление кода

```bash
# 1. Переключиться на новую версию
cd /opt/zakaz_dashboard
git pull origin main

# 2. Обновить зависимости (если нужно)
pip install -r requirements.txt

# 3. Перезапустить все таймеры
sudo ./manage_timers.sh restart qtickets
sudo ./manage_timers.sh restart vk_ads
sudo ./manage_timers.sh restart direct
sudo ./manage_timers.sh restart alerts

# 4. Перезапустить healthcheck сервер
sudo systemctl restart healthcheck.service
```

### Резервное копирование

```bash
# Проверить статус бэкапов
cd /opt/zakaz_dashboard/ops
./backup_verify.py

# Вручную создать бэкап при необходимости
./backup_full.sh

# Восстановление из бэкапа
./restore_test.sh
```

## Мониторинг

### Ключевые метрики

1. **Свежесть данных**:
   ```sql
   SELECT * FROM zakaz.v_data_freshness ORDER BY days_behind DESC;
   ```

2. **Успешность запусков**:
   ```sql
   SELECT 
       job,
       countIf(status = 'success') as success,
       countIf(status = 'error') as errors,
       success * 100.0 / (success + errors) as success_rate
   FROM zakaz.meta_job_runs
   WHERE started_at >= today() - 7
   GROUP BY job;
   ```

3. **Производительность**:
   ```sql
   SELECT 
       job,
       avg(JSONExtractInt(metrics, 'duration')) as avg_duration,
       max(JSONExtractInt(metrics, 'duration')) as max_duration
   FROM zakaz.meta_job_runs
   WHERE started_at >= today() - 7
     AND status = 'success'
   GROUP BY job;
   ```

### Алерты

Система автоматически отправляет алерты при:
- Неудачных запусках задач
- Устаревших данных (отставание > 2 дней)
- Проблемах со здоровьем системы

Проверка алертов:
```sql
SELECT * FROM zakaz.alerts 
WHERE created_at >= today() - 7
ORDER BY created_at DESC;
```

## Восстановление после сбоев

### Сценарий восстановления

1. **Кратковременный сбой API**:
   - Система автоматически повторит запросы
   - Таймеры перезапустятся при следующем запуске

2. **Длительный сбой источника**:
   - Включить Gmail резервный канал:
     ```bash
     sudo ./manage_timers.sh enable gmail
     ```
   - Настроить увеличенные интервалы проверки

3. **Проблемы с ClickHouse**:
   - Проверить доступность:
     ```bash
     curl http://localhost:8080/healthz
     ```
   - Перезапустить сервис:
     ```bash
     sudo systemctl restart clickhouse-server
     ```

4. **Полное восстановление системы**:
   ```bash
   # 1. Остановить все таймеры
   for timer in qtickets vk_ads direct gmail alerts; do
       sudo ./manage_timers.sh disable $timer
   done
   
   # 2. Восстановить данные из бэкапа
   ./restore_test.sh
   
   # 3. Проверить работоспособность
   curl http://localhost:8080/healthz
   
   # 4. Включить таймеры
   for timer in qtickets vk_ads direct alerts; do
       sudo ./manage_timers.sh enable $timer
   done
   ```

## Контакты

- **Email для алертов**: ads-irsshow@yandex.ru
- **Документация**: `docs/`
- **Логи**: systemd journal и файлы в `logs/`

## Чеклист для инцидентов

- [ ] Проверить статус всех таймеров
- [ ] Просмотреть логи проблемных компонентов
- [ ] Проверить свежесть данных
- [ ] Выполнить ручной запуск проблемного загрузчика
- [ ] Проверить метаданные о запусках
- [ ] Проверить healthcheck эндпоинты
- [ ] При необходимости включить резервные каналы
- [ ] Обновить документацию о решении проблемы
- [ ] Сообщить заинтересованным сторонам о решении