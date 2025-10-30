# РУКОВОДСТВО ПО МИГРАЦИИ СО СТАРОГО КОДА НА НОВУЮ ВЕРСИЮ

## Обзор

Данное руководство предназначено для плавной миграции с существующей системы Zakaz Dashboard на новую версию. Процесс миграции включает сохранение исторических данных, обновление конфигурации и проверку работоспособности.

## Предварительные требования

### Анализ текущей системы

Перед началом миграции необходимо:

1. **Определить версию текущей системы**
2. **Собрать информацию о существующих данных**
3. **Зафиксировать текущие конфигурации**
4. **Создать резервную копию**

### Проверка совместимости

```bash
# Проверка текущей версии
cd /opt/zakaz_dashboard
git log --oneline -5

# Проверка наличия миграционных скриптов
ls -la dashboard-mvp/infra/clickhouse/migrations/
```

---

## ЭТАП 1: ПОДГОТОВКА К МИГРАЦИИ

### 1.1 Создание полной резервной копии

```bash
# Создание бэкапа текущей системы
sudo mkdir -p /opt/zakaz_backup/$(date +%Y%m%d)
BACKUP_DIR="/opt/zakaz_backup/$(date +%Y%m%d)"

# Бэкап данных ClickHouse
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
BACKUP TO 'local://${BACKUP_DIR}/clickhouse_backup_before_migration'
FROM zakaz"

# Бэкап конфигурационных файлов
sudo cp -r /opt/zakaz_dashboard/secrets ${BACKUP_DIR}/
sudo cp -r /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse ${BACKUP_DIR}/clickhouse_config
sudo cp -r /etc/systemd/system/*zakaz* ${BACKUP_DIR}/systemd/

# Бэкап скриптов
sudo cp -r /opt/zakaz_dashboard/dashboard-mvp/ops ${BACKUP_DIR}/ops_scripts

echo "Резервная копия создана в ${BACKUP_DIR}"
```

### 1.2 Остановка текущих сервисов

```bash
# Остановка всех таймеров
sudo systemctl stop qtickets*.timer
sudo systemctl stop vk_ads*.timer
sudo systemctl stop direct*.timer
sudo systemctl stop alerts*.timer

# Остановка ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
docker-compose down

# Проверка остановки
docker ps -a | grep zakaz
systemctl list-timers | grep zakaz
```

---

## ЭТАП 2: ОБНОВЛЕНИЕ КОДА

### 2.1 Скачивание новой версии

```bash
# Сохранение текущей версии
cd /opt/zakaz_dashboard
git checkout -b backup_before_migration_$(date +%Y%m%d)

# Получение последней версии
git fetch origin
git checkout main
git pull origin main

# Проверка версии
git log --oneline -3
```

### 2.2 Проверка изменений в конфигурации

```bash
# Сравнение конфигурационных файлов
diff -u /opt/zakaz_backup/$(date +%Y%m%d)/clickhouse_config/users.d/00-admin.xml \
        dashboard-mvp/infra/clickhouse/users.d/00-admin.xml

diff -u /opt/zakaz_backup/$(date +%Y%m%d)/clickhouse_config/users.d/10-service-users.xml \
        dashboard-mvp/infra/clickhouse/users.d/10-service-users.xml
```

### 2.3 Обновление конфигурационных файлов

```bash
# Резервирование текущих конфигураций
sudo mv /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/00-admin.xml \
        /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/00-admin.xml.backup

# Копирование новых конфигураций
sudo cp dashboard-mvp/infra/clickhouse/users.d/00-admin.xml \
        dashboard-mvp/infra/clickhouse/users.d/10-service-users.xml \
        dashboard-mvp/infra/clickhouse/users.d/

# Проверка прав доступа
sudo chown root:root /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/*.xml
sudo chmod 644 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/*.xml
```

---

## ЭТАП 3: МИГРАЦИЯ ДАННЫХ CLICKHOUSE

### 3.1 Запуск ClickHouse с новой конфигурацией

```bash
# Обновление файла .env
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
cp .env.example .env

# Редактирование .env с сохранением текущих паролей
nano .env
```

Важно сохранить текущие пароли из файла `.env.backup`:
```bash
CLICKHOUSE_ADMIN_USER=admin
CLICKHOUSE_ADMIN_PASSWORD=ТЕКУЩИЙ_ПАРОЛЬ_АДМИНА
CLICKHOUSE_DB=zakaz
CLICKHOUSE_TZ=Europe/Moscow
```

```bash
# Запуск ClickHouse
docker-compose up -d

# Ожидание запуска
sleep 30

# Проверка доступности
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "SELECT 1"
```

### 3.2 Применение миграций схемы

```bash
# Применение новой схемы
cd /opt/zakaz_dashboard
bash dashboard-mvp/scripts/bootstrap_clickhouse.sh

# Проверка результата
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
SELECT 
    table,
    engine,
    count() as rows
FROM system.tables 
WHERE database = 'zakaz' 
GROUP BY table, engine
ORDER BY table"
```

### 3.3 Проверка целостности данных

```bash
# Проверка наличия исторических данных
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
SELECT 
    'stg_qtickets_sales' as table_name,
    count() as rows,
    min(event_date) as min_date,
    max(event_date) as max_date
FROM zakaz.stg_qtickets_sales

UNION ALL

SELECT 
    'fact_vk_ads_daily' as table_name,
    count() as rows,
    min(stat_date) as min_date,
    max(stat_date) as max_date
FROM zakaz.fact_vk_ads_daily

UNION ALL

SELECT 
    'fact_direct_daily' as table_name,
    count() as rows,
    min(stat_date) as min_date,
    max(stat_date) as max_date
FROM zakaz.fact_direct_daily"
```

---

## ЭТАП 4: МИГРАЦИЯ КОНФИГУРАЦИИ ИНТЕГРАЦИЙ

### 4.1 Обновление файлов секретов

```bash
# Проверка текущих файлов секретов
ls -la /opt/zakaz_dashboard/secrets/

# Создание новых файлов на основе старых
if [ -f "/opt/zakaz_dashboard/secrets/.env.qtickets" ]; then
    cp /opt/zakaz_dashboard/secrets/.env.qtickets \
       /opt/zakaz_dashboard/secrets/.env.qtickets_api.new
    echo "Найден старый файл .env.qtickets, создан .env.qtickets_api.new"
fi

# Обновление формата файла QTickets API
if [ -f "/opt/zakaz_dashboard/secrets/.env.qtickets_api.new" ]; then
    cat > /opt/zakaz_dashboard/secrets/.env.qtickets_api << EOF
# QTickets API конфигурация (мигрировано)
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_TOKEN=$(grep QTICKETS_TOKEN /opt/zakaz_dashboard/secrets/.env.qtickets_api.new | cut -d'=' -f2)
QTICKETS_SINCE_HOURS=24
ORG_NAME=zakaz

# ClickHouse конфигурация
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=EtL2024!Strong#Pass
CLICKHOUSE_DATABASE=zakaz

# Системные настройки
TZ=Europe/Moscow
REPORT_TZ=Europe/Moscow
JOB_NAME=qtickets_api
DRY_RUN=false
EOF
fi
```

### 4.2 Проверка и обновление токенов

```bash
# Проверка наличия всех необходимых токенов
REQUIRED_FILES=(
    ".env.qtickets_api"
    ".env.vk"
    ".env.direct"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "/opt/zakaz_dashboard/secrets/$file" ]; then
        echo "ОШИБКА: Отсутствует файл /opt/zakaz_dashboard/secrets/$file"
        echo "Создайте его на основе .env.sample файлов"
    else
        echo "✓ Файл $file найден"
    fi
done
```

---

## ЭТАП 5: СБОРКА И ЗАПУСК НОВЫХ СЕРВИСОВ

### 5.1 Сборка Docker-образов

```bash
# Сборка образа QTickets API
cd /opt/zakaz_dashboard
docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# Проверка образа
docker images | grep qtickets_api
```

### 5.2 Тестовый запуск

```bash
# Тестовый запуск QTickets API в dry-run режиме
docker run --rm \
  --name qtickets_api_migration_test \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run

# Проверка логов
docker logs qtickets_api_migration_test
```

### 5.3 Обновление systemd юнитов

```bash
# Копирование новых юнитов
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.service /etc/systemd/system/
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение новых таймеров
sudo systemctl enable --now qtickets_api.timer
sudo systemctl enable --now vk_ads.timer
sudo systemctl enable --now direct.timer
```

---

## ЭТАП 6: ПРОВЕРКА РАБОТОСПОСОБНОСТИ

### 6.1 Запуск системной проверки

```bash
# Запуск скрипта проверки
cd /opt/zakaz_dashboard
bash dashboard-mvp/ops/system_check.sh
```

### 6.2 Проверка загрузки данных

```bash
# Ручной запуск для проверки
sudo systemctl start qtickets_api.service

# Ожидание завершения
sleep 60

# Проверка результатов
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
SELECT 
    job,
    started_at,
    status,
    rows_processed,
    message
FROM zakaz.meta_job_runs 
WHERE job = 'qtickets_api' 
ORDER BY started_at DESC 
LIMIT 3"
```

### 6.3 Проверка доступа DataLens

```bash
# Проверка HTTP доступа
curl -s -u "datalens_reader:ChangeMe123!" \
     "https://localhost/?query=SELECT%20count()%20FROM%20zakaz.v_sales_latest"

# Проверка прав
docker exec ch-zakaz clickhouse-client --user=datalens_reader --password='ChangeMe123!' -q "SHOW GRANTS"
```

---

## ЭТАП 7: МОНИТОРИНГ ПОСЛЕ МИГРАЦИИ

### 7.1 Первые 24 часа

```bash
# Мониторинг логов
journalctl -u qtickets_api.service -f
journalctl -u vk_ads.service -f
journalctl -u direct.service -f

# Проверка данных каждые 6 часов
for i in {1..4}; do
    echo "=== Проверка $i из 4 ==="
    docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
    SELECT 
        'qtickets_api' as source,
        count() as rows,
        max(sale_ts) as latest
    FROM zakaz.stg_qtickets_api_orders_raw
    WHERE sale_ts > now() - INTERVAL 1 DAY"
    sleep 21600  # 6 часов
done
```

### 7.2 Еженедельная проверка

```bash
# Скрипт для еженедельной проверки
cat > /opt/zakaz_dashboard/ops/weekly_migration_check.sh << 'EOF'
#!/bin/bash
echo "=== Еженедельная проверка после миграции ==="
DATE=$(date +%Y-%m-%d)

# Проверка свежести данных
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
SELECT 
    'Data Freshness Check' as metric,
    source,
    latest_date,
    days_behind,
    CASE 
        WHEN days_behind <= 1 THEN 'OK'
        WHEN days_behind <= 3 THEN 'WARNING'
        ELSE 'CRITICAL'
    END as status
FROM (
    SELECT 
        'qtickets_api' as source,
        max(sale_ts) as latest_date,
        dateDiff('day', max(sale_ts), today()) as days_behind
    FROM zakaz.stg_qtickets_api_orders_raw
    
    UNION ALL
    
    SELECT 
        'vk_ads' as source,
        max(stat_date) as latest_date,
        dateDiff('day', max(stat_date), today()) as days_behind
    FROM zakaz.fact_vk_ads_daily
)"

# Проверка ошибок
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
SELECT 
    'Error Check' as metric,
    count() as error_count,
    max(started_at) as last_error
FROM zakaz.meta_job_runs 
WHERE status = 'error' 
  AND started_at > today() - INTERVAL 7 DAY"
EOF

chmod +x /opt/zakaz_dashboard/ops/weekly_migration_check.sh
```

---

## ВОЗМОЖНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### Проблема: Несовместимость схемы данных

**Симптомы**: Ошибки при применении миграций, отсутствие таблиц

**Решение**:
```bash
# Проверка текущей схемы
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "SHOW TABLES FROM zakaz"

# Применение миграций вручную
docker exec -i ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' < dashboard-mvp/infra/clickhouse/migrations/2025-qtickets-api-final.sql
```

### Проблема: Потеря данных при миграции

**Симптомы**: Таблицы пустые после миграции

**Решение**:
```bash
# Восстановление из бэкапа
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
RESTORE FROM 'local:///opt/zakaz_backup/$(date +%Y%m%d)/clickhouse_backup_before_migration'
"

# Повторное применение миграций
bash dashboard-mvp/scripts/bootstrap_clickhouse.sh
```

### Проблема: Неработающие таймеры

**Симптомы**: Данные не обновляются

**Решение**:
```bash
# Проверка статуса таймеров
systemctl list-timers | grep zakaz

# Проверка конфигурации юнитов
systemctl cat qtickets_api.service

# Ручной запуск для отладки
sudo systemctl start qtickets_api.service
journalctl -u qtickets_api.service -n 50
```

### Проблема: Проблемы с доступом к DataLens

**Симптомы**: Ошибки аутентификации в DataLens

**Решение**:
```bash
# Проверка пользователя
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
SELECT 
    name,
    auth_type,
    host_ip
FROM system.users 
WHERE name = 'datalens_reader'"

# Сброс пароля
docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
ALTER USER datalens_reader IDENTIFIED BY 'ChangeMe123!'"
```

---

## ОТКАТ МИГРАЦИИ

Если миграция прошла неудачно:

### 7.1 Полный откат

```bash
# Остановка новых сервисов
sudo systemctl stop qtickets_api.timer vk_ads.timer direct.timer alerts.timer
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
docker-compose down

# Восстановление кода
git checkout backup_before_migration_$(date +%Y%m%d)

# Восстановление конфигурации
sudo cp /opt/zakaz_backup/$(date +%Y%m%d)/clickhouse_config/users.d/* \
        dashboard-mvp/infra/clickhouse/users.d/

# Восстановление данных
docker-compose up -d
sleep 30

docker exec ch-zakaz clickhouse-client --user=admin --password='ТЕКУЩИЙ_ПАРОЛЬ' -q "
RESTORE FROM 'local:///opt/zakaz_backup/$(date +%Y%m%d)/clickhouse_backup_before_migration'"

# Восстановление сервисов
sudo cp /opt/zakaz_backup/$(date +%Y%m%d)/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now qtickets.timer vk_ads.timer direct.timer
```

### 7.2 Частичный откат

```bash
# Откат только конфигурации
sudo cp /opt/zakaz_backup/$(date +%Y%m%d)/secrets/* /opt/zakaz_dashboard/secrets/

# Откат systemd юнитов
sudo cp /opt/zakaz_backup/$(date +%Y%m%d)/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
```

---

## ЗАВЕРШЕНИЕ МИГРАЦИИ

После успешной миграции:

1. ✅ **Все данные сохранены** и доступны
2. ✅ **Новые сервисы** работают корректно
3. ✅ **Таймеры** выполняются по расписанию
4. ✅ **DataLens** подключен к данным
5. ✅ **Мониторинг** работает

### Финальные шаги

```bash
# Удаление временных файлов
sudo rm -f /opt/zakaz_dashboard/secrets/.env.qtickets_api.new

# Создание отметки об успешной миграции
echo "Миграция успешно завершена: $(date)" > /opt/zakaz_dashboard/migration_completed.txt

# Архивация бэкапа
sudo tar -czf /opt/zakaz_backup/migration_backup_$(date +%Y%m%d).tar.gz \
        /opt/zakaz_backup/$(date +%Y%m%d)/

# Очистка
sudo rm -rf /opt/zakaz_backup/$(date +%Y%m%d)/
```

---

## ПОДДЕРЖКА ПОСЛЕ МИГРАЦИИ

### Период мониторинга

- **Первые 24 часа**: Непрерывный мониторинг
- **Первая неделя**: Ежедневные проверки
- **Первый месяц**: Еженедельные проверки

### Контакты для поддержки

- **Техническая поддержка**: [контакт разработчика]
- **Экстренные случаи**: [экстренный контакт]
- **Вопросы по миграции**: [контакт миграционной команды]

---

**Версия документа**: 1.0.0  
**Дата создания**: $(date +%Y-%m-%d)  
**Последнее обновление**: $(date +%Y-%m-%d)