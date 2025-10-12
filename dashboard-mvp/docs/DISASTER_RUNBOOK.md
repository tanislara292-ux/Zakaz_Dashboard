# Disaster Runbook

## Обзор

Этот документ содержит пошаговые инструкции для восстановления системы после критических сбоев. Цель - минимизировать время простоя и потерю данных.

## SLA и цели

- **RPO (Recovery Point Objective)**: ≤ 1 час (максимальная потеря данных)
- **RTO (Recovery Time Objective)**: ≤ 2 часа (максимальное время восстановления)
- **Доступность системы**: 99.9% (допустимый простой 8.76 часов в месяц)

## Классификация инцидентов

### Уровень 1: Критический (P0)
- Полная недоступность системы
- Потеря данных
- Влияние на всех пользователей

### Уровень 2: Высокий (P1)
- Частичная недоступность
- Деградация производительности
- Влияние на большинство пользователей

### Уровень 3: Средний (P2)
- Ограниченная функциональность
- Влияние на некоторых пользователей

### Уровень 4: Низкий (P3)
- Минимальные проблемы
- Работаaround доступен

## Команда реагирования

### Роли и ответственности

| Роль | Ответственный | Контакты | Обязанности |
|------|--------------|----------|-------------|
| Инцидент-менеджер | [Имя] | +7-XXX-XXX-XX-XX | Координация, коммуникация |
| DevOps инженер | [Имя] | +7-XXX-XXX-XX-XX | Инфраструктура, восстановление |
| Инженер данных | [Имя] | +7-XXX-XXX-XX-XX | Данные, ETL процессы |
| Разработчик | [Имя] | +7-XXX-XXX-XX-XX | Приложение, код |
| Руководитель проекта | [Имя] | +7-XXX-XXX-XX-XX | Принятие решений |

### Контакты в экстренной ситуации

- **Горячая линия**: +7-XXX-XXX-XX-XX (24/7)
- **DevOps дежурный**: +7-XXX-XXX-XX-XX
- **Инженер данных**: +7-XXX-XXX-XX-XX
- **Telegram чат**: https://t.me/zakaz_incidents

## Сценарии восстановления

### Сценарий 1: Отказ ClickHouse

#### Симптомы
- DataLens не подключается к ClickHouse
- ETL процессы завершаются с ошибками подключения
- Дашборды не отображают данные

#### Диагностика (5 минут)
```bash
# Проверка доступности ClickHouse
curl -I http://localhost:8123/?query=SELECT%201

# Проверка статуса контейнера
docker ps | grep clickhouse

# Проверка логов
docker logs ch-zakaz --tail 100
```

#### Действия

**Если ClickHouse не запущен** (15 минут):
```bash
# Перезапуск контейнера
docker-compose restart clickhouse

# Проверка после перезапуска
docker logs ch-zakaz --tail 50
```

**Если данные повреждены** (90 минут):
```bash
# Остановка ClickHouse
docker-compose stop clickhouse

# Сохранение текущих данных (для анализа)
cp -r /opt/clickhouse/data /opt/clickhouse/data_corrupted_$(date +%Y%m%d_%H%M%S)

# Очистка данных
rm -rf /opt/clickhouse/data/*

# Запуск ClickHouse
docker-compose start clickhouse

# Ожидание запуска
sleep 30

# Восстановление из последнего бэкапа
docker exec ch-zakaz clickhouse-client --user backup_user --password ${CLICKHOUSE_BACKUP_USER_PASSWORD} --query "
    RESTORE DATABASE zakaz, DATABASE bi, DATABASE meta 
    FROM S3('${S3_BUCKET}', '${S3_ACCESS_KEY}', '${S3_SECRET_KEY}', 'prefix=clickhouse-backups/') 
    AS '${LAST_FULL_BACKUP}'
"
```

#### Проверка восстановления (15 минут)
```bash
# Проверка таблиц
docker exec ch-zakaz clickhouse-client --query "SHOW TABLES FROM zakaz"
docker exec ch-zakaz clickhouse-client --query "SHOW TABLES FROM bi"
docker exec ch-zakaz clickhouse-client --query "SHOW TABLES FROM meta"

# Проверка данных
docker exec ch-zakaz clickhouse-client --query "SELECT count() FROM zakaz.dm_sales_daily LIMIT 5"
docker exec ch-zakaz clickhouse-client --query "SELECT count() FROMzakaz.dm_vk_ads_daily LIMIT 5"
```

### Сценарий 2: Отказ сервера

#### Симптомы
- Все сервисы недоступны
- Нет ответа по SSH
- Мониторинг показывает недоступность сервера

#### Диагностика (5 минут)
```bash
# Проверка доступности сервера
ping server_hostname

# Проверка сервисов с внешнего хоста
curl -I https://ch.your-domain/
```

#### Действия

**Восстановление на новом сервере** (120 минут):

1. **Подготовка нового сервера** (30 минут)
   ```bash
   # Установка Docker и Docker Compose
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   
   # Установка Docker Compose
   pip install docker-compose
   
   # Создание директорий
   mkdir -p /opt/zakaz_dashboard
   cd /opt/zakaz_dashboard
   ```

2. **Разворачивание инфраструктуры** (45 минут)
   ```bash
   # Клонирование репозитория
   git clone https://github.com/your-org/zakaz_dashboard.git .
   
   # Настройка переменных окружения
   cp .env.sample .env
   # Редактирование .env с реальными значениями
   
   # Запуск ClickHouse
   cd infra/clickhouse
   docker-compose up -d
   
   # Ожидание запуска
   sleep 60
   ```

3. **Восстановление данных** (30 минут)
   ```bash
   # Восстановление из последнего бэкапа
   docker exec ch-zakaz clickhouse-client --user backup_user --password ${CLICKHOUSE_BACKUP_USER_PASSWORD} --query "
       RESTORE DATABASE zakaz, DATABASE bi, DATABASE meta 
       FROM S3('${S3_BUCKET}', '${S3_ACCESS_KEY}', '${S3_SECRET_KEY}', 'prefix=clickhouse-backups/') 
       AS '${LAST_FULL_BACKUP}'
   "
   
   # Проверка данных
   docker exec ch-zakaz clickhouse-client --query "SELECT count() FROM zakaz.dm_sales_daily"
   ```

4. **Настройка Caddy и домена** (15 минут)
   ```bash
   # Обновление DNS для指向 на новый сервер
   # Обновление Caddyfile с новым доменом (если нужно)
   
   # Перезапуск Caddy
   docker-compose restart caddy
   ```

#### Проверка восстановления (15 минут)
```bash
# Проверка доступности ClickHouse
curl -I https://ch.your-domain/?query=SELECT%201

# Проверка DataLens
# Открыть дашборд и проверить данные

# Проверка ETL процессов
cd /opt/zakaz_dashboard
./ops/run_job.sh cdc_qtickets
./ops/run_job.sh cdc_vk
```

### Сценарий 3: Утечка или повреждение данных

#### Симптомы
- Некорректные данные в дашбордах
- Резкие изменения в метриках
- Ошибки в ETL процессах

#### Диагностика (15 минут)
```sql
-- Проверка целостности данных
SELECT 
    event_date,
    count() as row_count,
    sum(net_revenue) as total_revenue
FROM zakaz.dm_sales_daily
WHERE event_date >= today() - 7
GROUP BY event_date
ORDER BY event_date DESC;

-- Проверка последних загрузок
SELECT 
    job,
    started_at,
    status,
    rows_written,
    err_msg
FROM meta.etl_runs
ORDER BY started_at DESC
LIMIT 10;
```

#### Действия

**Определение момента повреждения** (15 минут):
```bash
# Анализ логов ETL процессов
journalctl -u etl@* --since "1 day ago" | grep -i error

# Проверка времени последнего успешного прогона
clickhouse-client --query "
    SELECT job, max(started_at) as last_success 
    FROM meta.etl_runs 
    WHERE status = 'ok' 
    GROUP BY job"
```

**Восстановление данных** (60 минут):
```bash
# Восстановление из бэкапа до момента повреждения
docker exec ch-zakaz clickhouse-client --user backup_user --password ${CLICKHOUSE_BACKUP_USER_PASSWORD} --query "
    RESTORE DATABASE zakaz, DATABASE bi, DATABASE meta 
    FROM S3('${S3_BUCKET}', '${S3_ACCESS_KEY}', '${S3_SECRET_KEY}', 'prefix=clickhouse-backups/') 
    AS '${BACKUP_BEFORE_DAMAGE}'
"

# Перезапуск ETL процессов для догрузки данных
./ops/run_job.sh cdc_qtickets
./ops/run_job.sh cdc_vk
./ops/run_job.sh build_dm_sales_incr
./ops/run_job.sh build_dm_vk_incr
```

## Коммуникация во время инцидента

### Шаблон уведомления

**Тема**: [URGENT] Инцидент с системой Zakaz - [Описание проблемы]

**Содержание**:
```
Статус: [Investigating/Mitigated/Resolved]
Время начала: [YYYY-MM-DD HH:MM:SS]
Влияние: [Описание влияния на пользователей]
Текущие действия: [Что делаем для решения]
Ожидаемое время восстановления: [ETA]
Следующее обновление: [Время следующего обновления]
```

### Каналы коммуникации

1. **Внутренняя команда**
   - Telegram чат: https://t.me/zakaz_incidents
   - Созвон по необходимости

2. **Внешние стейкхолдеры**
   - Email: stakeholders@company.com
   - Статус-страница: https://status.company.com

## Пост-инцидентный анализ

### Шаблон пост-мортема

1. **Обзор инцидента**
   - Время начала и окончания
   - Длительность простоя
   - Влияние на пользователей

2. **Хронология событий**
   - Временная шкала событий
   - Ключевые действия и решения

3. **Корневая причина**
   - Что вызвало инцидент
   - Почему это произошло

4. **Влияние**
   - Техническое влияние
   - Бизнес-влияние
   - Пользовательский опыт

5. **Уроки извлеченные**
   - Что пошло хорошо
   - Что можно улучшить

6. **Действия по предотвращению**
   - Краткосрочные действия
   - Долгосрочные улучшения

### Пример пост-мортема

См. `docs/templates/postmortem.md` для полного шаблона.

## Подготовка к инцидентам

### Регулярные тренировки

1. **Ежемесячные tabletop упражнения**
   - Обсуждение сценариев инцидентов
   - Проверка знаний процедур

2. **Квартальные симуляции**
   - Полное моделирование инцидента
   - Практика восстановления

### Проверка готовности

1. **Еженедельно**
   - Проверка доступности бэкапов
   - Проверка работоспособности алертов

2. **Ежемесячно**
   - Тестовое восстановление
   - Обновление контактов

3. **Квартально**
   - Полное тестирование DR плана
   - Обновление документации

## Инструменты и ресурсы

### Мониторинг
- Grafana: https://grafana.company.com
- AlertManager: https://alerts.company.com
- Логи: https://logs.company.com

### Доступы
- SSH ключи: `secrets/ssh_keys/`
- Пароли: `secrets/passwords/`
- API ключи: `secrets/api_keys/`

### Документация
- Архитектура: `docs/ARCHITECTURE.md`
- Runbooks: `docs/RUNBOOK_*.md`
- Контактная информация: `docs/CONTACTS.md`

## Проверочный лист для восстановления

### Начало инцидента (0-5 минут)
- [ ] Определить уровень инцидента
- [ ] Собрать команду реагирования
- [ ] Начать запись событий
- [ ] Оценить влияние

### Диагностика (5-15 минут)
- [ ] Собрать логи и метрики
- [ ] Определить корневую причину
- [ ] Оценить объем повреждений

### Восстановление (15-120 минут)
- [ ] Выбрать стратегию восстановления
- [ ] Выполнить восстановление
- [ ] Проверить результат

### Завершение (120-135 минут)
- [ ] Проверить работоспособность системы
- [ ] Уведомить стейкхолдеров
- [ ] Начать пост-инцидентный анализ

## Заключение

Этот Disaster Runbook является живым документом и должен регулярно обновляться. Регулярные тренировки и проверки готовности гарантируют, что команда сможет эффективно реагировать на инциденты и минимизировать влияние на бизнес.

## Версия и история

| Версия | Дата | Изменения | Автор |
|--------|------|-----------|-------|
| 1.0 | 2025-10-11 | Первая версия | [Имя] |
| | | | |