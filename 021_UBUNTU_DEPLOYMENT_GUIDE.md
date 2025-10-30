# ПОЛНОЕ РУКОВОДСТВО ПО РАЗВЕРТЫВАНИЮ ZAKAZ DASHBOARD НА UBUNTU SERVER

## Обзор

Данное руководство предназначено для полного развертывания системы Zakaz Dashboard на сервере заказчика с Ubuntu Linux. Система включает:

- **ClickHouse** - основная база данных для аналитики
- **QTickets API** - загрузчик данных о продажах и инвентаре
- **VK Ads API** - загрузчик маркетинговых данных
- **Яндекс.Директ API** - загрузчик рекламных данных
- **Yandex DataLens** - BI-платформа для визуализации

## Предварительные требования

### Аппаратные требования

- **CPU**: Минимум 4 ядра (рекомендуется 8+)
- **RAM**: Минимум 8GB (рекомендуется 16GB+)
- **Диск**: Минимум 100GB SSD (рекомендуется 500GB+)
- **Сеть**: Стабильное интернет-соединение

### Программные требования

- **Ubuntu**: 20.04 LTS или новее
- **Docker**: 20.10+ и Docker Compose 2.0+
- **Git**: 2.25+
- **Пользователь**: с правами sudo

### Сетевые требования

- **Порты**: 80, 443 (для HTTPS), 8123 (ClickHouse HTTP), 9000 (ClickHouse Native)
- **Домен**: bi.zakaz-dashboard.ru (или другой домен заказчика)
- **SSL**: Сертификат для домена (можно использовать Let's Encrypt)

---

## ЭТАП 1: ПОДГОТОВКА СЕРВЕРА

### 1.1 Обновление системы

```bash
# Подключитесь к серверу по SSH
ssh user@server_ip

# Обновите систему
sudo apt update && sudo apt upgrade -y

# Перезагрузите систему
sudo reboot
```

### 1.2 Установка Docker и Docker Compose

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version
```

### 1.3 Установка дополнительных пакетов

```bash
# Установка необходимых утилит
sudo apt install -y git curl wget htop unzip python3 python3-pip

# Установка Python зависимостей
sudo pip3 install clickhouse-driver requests pandas python-dotenv
```

### 1.4 Настройка файрвола

```bash
# Настройка UFW
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8123/tcp  # ClickHouse HTTP (опционально, только для локального доступа)
sudo ufw enable
```

---

## ЭТАП 2: РАЗВЕРТЫВАНИЕ РЕПОЗИТОРИЯ

### 2.1 Клонирование репозитория

```bash
# Создание директории для проекта
sudo mkdir -p /opt/zakaz_dashboard
sudo chown $USER:$USER /opt/zakaz_dashboard

# Клонирование репозитория
cd /opt/zakaz_dashboard
git clone https://github.com/tanislara292-ux/Zakaz_Dashboard.git .

# Переключение на последнюю стабильную ветку
git checkout main
git pull origin main
```

### 2.2 Создание структуры директорий

```bash
# Создание необходимых директорий
mkdir -p /opt/zakaz_dashboard/secrets
mkdir -p /opt/zakaz_dashboard/logs
mkdir -p /opt/zakaz_dashboard/backups

# Установка прав доступа
chmod 700 /opt/zakaz_dashboard/secrets
chmod 755 /opt/zakaz_dashboard/logs
chmod 755 /opt/zakaz_dashboard/backups
```

---

## ЭТАП 3: НАСТРОЙКА CLICKHOUSE

### 3.1 Подготовка конфигурации ClickHouse

```bash
# Переход в директорию ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse

# Копирование файла окружения
cp .env.example .env

# Редактирование конфигурации
nano .env
```

Содержимое файла `.env`:
```bash
# Администратор ClickHouse
CLICKHOUSE_ADMIN_USER=admin
CLICKHOUSE_ADMIN_PASSWORD=СМЕНИТЕ_ЭТОТ_ПАРОЛЬ_НА_НАСТОЯЩИЙ
CLICKHOUSE_DB=zakaz
CLICKHOUSE_TZ=Europe/Moscow

# Порты (для внутреннего использования)
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_NATIVE_PORT=9000
```

### 3.2 Проверка конфигурационных файлов

```bash
# Проверка наличия критических файлов
ls -la users.d/
# Должны быть:
# - 00-admin.xml
# - 10-service-users.xml

# Проверка содержимого 00-admin.xml
cat users.d/00-admin.xml
# Убедитесь, что пароль admin_pass заменен на ваш пароль из .env
```

### 3.3 Запуск ClickHouse

```bash
# Запуск ClickHouse через Docker Compose
docker-compose up -d

# Проверка статуса
docker-compose ps

# Проверка логов
docker-compose logs -f clickhouse
```

### 3.4 Инициализация схемы базы данных

```bash
# Запуск скрипта инициализации
cd /opt/zakaz_dashboard
bash dashboard-mvp/scripts/bootstrap_clickhouse.sh

# Проверка результата
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SHOW TABLES FROM zakaz"
```

---

## ЭТАП 4: НАСТРОЙКА СЕКРЕТОВ И ТОКЕНОВ

### 4.1 Создание файла секретов QTickets API

```bash
# Создание файла конфигурации
nano /opt/zakaz_dashboard/secrets/.env.qtickets_api
```

Содержимое файла:
```bash
# QTickets API конфигурация
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_TOKEN=ВАШ_БОЕВОЙ_ТОКЕН_QTICKETS
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
DRY_RUN=false  # Изменить на true для тестирования
```

### 4.2 Создание файла секретов VK Ads

```bash
# Создание файла конфигурации
nano /opt/zakaz_dashboard/secrets/.env.vk
```

Содержимое файла:
```bash
# VK Ads API конфигурация
VK_ACCESS_TOKEN=ВАШ_ТОКЕН_VK_ADS
VK_ACCOUNT_ID=ВАШ_ACCOUNT_ID
VK_CLIENT_ID=ВАШ_CLIENT_ID

# ClickHouse конфигурация
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=EtL2024!Strong#Pass

# Системные настройки
TZ=Europe/Moscow
```

### 4.3 Создание файла секретов Яндекс.Директ

```bash
# Создание файла конфигурации
nano /opt/zakaz_dashboard/secrets/.env.direct
```

Содержимое файла:
```bash
# Яндекс.Директ API конфигурация
DIRECT_CLIENT_ID=ВАШ_CLIENT_ID
DIRECT_CLIENT_SECRET=ВАШ_CLIENT_SECRET
DIRECT_TOKEN=ВАШ_ТОКЕН_ЯНДЕКС_ДИРЕКТ
DIRECT_LOGIN=ВАШ_ЛОГИН

# ClickHouse конфигурация
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=EtL2024!Strong#Pass

# Системные настройки
TZ=Europe/Moscow
```

### 4.4 Установка прав доступа

```bash
# Установка прав на файлы секретов
chmod 600 /opt/zakaz_dashboard/secrets/.env*
chown $USER:$USER /opt/zakaz_dashboard/secrets/.env*
```

---

## ЭТАП 5: СБОРКА DOCKER-ОБРАЗОВ

### 5.1 Сборка образа QTickets API

```bash
# Переход в директорию проекта
cd /opt/zakaz_dashboard

# Сборка образа
docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# Проверка образа
docker images | grep qtickets_api
```

### 5.2 Тестовый запуск QTickets API

```bash
# Запуск в режиме dry-run для проверки
docker run --rm \
  --name qtickets_api_test \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run

# Проверка логов
docker logs qtickets_api_test
```

---

## ЭТАП 6: НАСТРОЙКА SYSTEMD СЕРВИСОВ

### 6.1 Создание пользователя ETL

```bash
# Создание пользователя для запуска ETL процессов
sudo useradd -m -s /bin/bash etl
sudo usermod -aG docker etl

# Предоставление прав на директорию проекта
sudo chown -R etl:etl /opt/zakaz_dashboard
```

### 6.2 Установка systemd юнитов

```bash
# Копирование файлов юнитов
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.service /etc/systemd/system/
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload
```

### 6.3 Включение и запуск таймеров

```bash
# Включение таймеров
sudo systemctl enable --now qtickets_api.timer
sudo systemctl enable --now vk_ads.timer
sudo systemctl enable --now direct.timer

# Проверка статуса таймеров
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'
```

---

## ЭТАП 7: НАСТРОЙКА HTTPS ДОСТУПА

### 7.1 Установка Caddy (веб-сервер с автоматическим SSL)

```bash
# Установка Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy -y
```

### 7.2 Настройка Caddyfile

```bash
# Создание Caddyfile
sudo nano /etc/caddy/Caddyfile
```

Содержимое Caddyfile:
```caddyfile
bi.zakaz-dashboard.ru {
    reverse_proxy localhost:8123 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
    
    # Логирование
    log {
        output file /var/log/caddy/zakaz-dashboard.log {
            roll_size 100mb
            roll_keep 5
        }
        format json
    }
}

# Опционально: Healthcheck endpoint
bi.zakaz-dashboard.ru/healthz {
    respond "OK" 200
}
```

### 7.3 Запуск Caddy

```bash
# Запуск Caddy
sudo systemctl enable --now caddy

# Проверка статуса
sudo systemctl status caddy

# Проверка HTTPS доступа
curl -k https://bi.zakaz-dashboard.ru/?query=SELECT%201
```

---

## ЭТАП 8: ПРОВЕРКА РАБОТОСПОСОБНОСТИ СИСТЕМЫ

### 8.1 Запуск системной проверки

```bash
# Запуск скрипта проверки
cd /opt/zakaz_dashboard
bash dashboard-mvp/ops/system_check.sh
```

### 8.2 Проверка данных в ClickHouse

```bash
# Подключение к ClickHouse
docker exec -it ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ'

# Проверка таблиц
SHOW TABLES FROM zakaz;

# Проверка свежести данных
SELECT 
    'qtickets_api' as source,
    max(sale_ts) as latest_date,
    count() as total_rows
FROM zakaz.stg_qtickets_api_orders_raw;

# Проверка прав пользователя datalens_reader
SHOW GRANTS FOR datalens_reader;
```

### 8.3 Проверка работы таймеров

```bash
# Проверка статуса таймеров
systemctl list-timers --all

# Проверка логов конкретного сервиса
journalctl -u qtickets_api.service --since "1 hour ago" -n 50
```

---

## ЭТАП 9: НАСТРОЙКА МОНИТОРИНГА И АЛЕРТОВ

### 9.1 Настройка алертов

```bash
# Создание файла конфигурации алертов
nano /opt/zakaz_dashboard/secrets/.env.alerts
```

Содержимое файла:
```bash
# Email для алертов
ALERT_EMAIL=ads-irsshow@yandex.ru
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=587
SMTP_USER=ads-irsshow@yandex.ru
SMTP_PASSWORD=ВАШ_ПАРОЛЬ_ЯНДЕКС_ПОЧТЫ

# ClickHouse конфигурация
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=EtL2024!Strong#Pass
```

### 9.2 Включение таймера алертов

```bash
# Копирование юнита алертов
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/alerts.service /etc/systemd/system/
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/alerts.timer /etc/systemd/system/

# Включение таймера
sudo systemctl enable --now alerts.timer
```

---

## ЭТАП 10: НАСТРОЙКА РЕЗЕРВНОГО КОПИРОВАНИЯ

### 10.1 Создание скрипта бэкапа

```bash
# Создание скрипта бэкапа
sudo nano /opt/zakaz_dashboard/ops/backup_full.sh
```

Содержимое скрипта:
```bash
#!/bin/bash
# Полный бэкап ClickHouse

BACKUP_DIR="/opt/zakaz_dashboard/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="zakaz_backup_${DATE}"

# Создание бэкапа
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
BACKUP TO 'local://${BACKUP_DIR}/${BACKUP_NAME}'
FROM zakaz
SETTINGS async_insert=0, max_threads=4"

# Очистка старых бэкапов (оставляем последние 7)
find ${BACKUP_DIR} -name "zakaz_backup_*" -type d -mtime +7 -exec rm -rf {} \;

echo "Бэкап ${BACKUP_NAME} создан успешно"
```

### 10.2 Настройка крона для бэкапов

```bash
# Добавление в crontab
sudo crontab -e

# Добавить строку для ежедневного бэкапа в 3:00
0 3 * * * /opt/zakaz_dashboard/ops/backup_full.sh >> /opt/zakaz_dashboard/logs/backup.log 2>&1
```

---

## ЭТАП 11: ПОДКЛЮЧЕНИЕ К YANAS DETALENS

### 11.1 Параметры подключения для DataLens

- **Хост**: `bi.zakaz-dashboard.ru`
- **Порт**: `443`
- **База данных**: `zakaz`
- **Имя пользователя**: `datalens_reader`
- **Пароль**: `ChangeMe123!`
- **Использовать HTTPS**: ✅

### 11.2 SQL-запросы для DataLens

Основные представления для дашбордов:

```sql
-- Продажи (актуальные данные)
SELECT
    event_date,
    city,
    event_name,
    tickets_sold,
    revenue,
    refunds_amount,
    (revenue - refunds_amount) AS net_revenue
FROM zakaz.v_qtickets_sales_latest

-- Маркетинговые данные
SELECT
    d,
    city,
    spend_total,
    net_revenue,
    romi
FROM zakaz.v_marketing_daily

-- Инвентарь
SELECT
    event_id,
    event_name,
    city,
    tickets_total,
    tickets_left,
    (tickets_total - tickets_left) AS tickets_sold
FROM zakaz.v_qtickets_inventory
```

---

## ТРАБЛШУТИНГ

### Проблема: ClickHouse не запускается

```bash
# Проверка логов
docker-compose logs clickhouse

# Проверка конфигурации
docker exec ch-zakaz clickhouse-client --query "SHOW SETTINGS"

# Перезапуск
docker-compose restart clickhouse
```

### Проблема: QTickets API не загружает данные

```bash
# Проверка токена
curl -H "Authorization: Bearer ВАШ_ТОКЕН" \
     "https://qtickets.ru/api/rest/v1/orders?limit=1"

# Проверка логов
journalctl -u qtickets_api.service -n 50

# Ручной запуск
docker run --rm \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run
```

### Проблема: HTTPS не работает

```bash
# Проверка статуса Caddy
sudo systemctl status caddy

# Проверка логов Caddy
sudo journalctl -u caddy -n 50

# Проверка конфигурации
sudo caddy validate --config /etc/caddy/Caddyfile

# Тест локально
curl -k https://localhost:443/?query=SELECT%201
```

### Проблема: Нет данных в ClickHouse

```bash
# Проверка прав пользователя
docker exec ch-zakaz clickhouse-client \
  --user=etl_writer \
  --password='EtL2024!Strong#Pass' \
  -q "SHOW GRANTS"

# Проверка таблиц
docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  -q "SHOW TABLES FROM zakaz"

# Проверка последних запусков
docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  -q "SELECT * FROM zakaz.meta_job_runs ORDER BY started_at DESC LIMIT 5"
```

---

## МОНИТОРИНГ И ПОДДЕРЖКА

### Ежедневные проверки

```bash
# Запуск полной проверки системы
bash /opt/zakaz_dashboard/dashboard-mvp/ops/system_check.sh

# Проверка свежести данных
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "
SELECT 
    source,
    latest_date,
    days_behind
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
```

### Полезные команды

```bash
# Статус всех контейнеров
docker ps -a

# Логи конкретного контейнера
docker logs -f ch-zakaz

# Перезапуск сервиса
sudo systemctl restart qtickets_api.service

# Просмотр таймеров
systemctl list-timers

# Мониторинг ресурсов
htop
df -h
docker stats
```

---

## БЕЗОПАСНОСТЬ

### Рекомендации по безопасности

1. **Измените пароли по умолчанию**:
   - admin/admin_pass в ClickHouse
   - datalens_reader/ChangeMe123!
   - etl_writer/EtL2024!Strong#Pass

2. **Ограничьте сетевой доступ**:
   - Закройте порт 8123 для внешнего доступа
   - Используйте только HTTPS (порт 443)

3. **Регулярно обновляйте систему**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   docker-compose pull
   docker-compose up -d
   ```

4. **Мониторьте логи**:
   ```bash
   # Логи безопасности
   sudo journalctl -u sshd -f
   
   # Логи ClickHouse
   docker logs ch-zakaz -f
   ```

---

## ЗАВЕРШЕНИЕ РАЗВЕРТЫВАНИЯ

После выполнения всех шагов:

1. ✅ **ClickHouse** работает и доступен по HTTPS
2. ✅ **Данные** загружаются из всех источников
3. ✅ **Таймеры** systemd работают корректно
4. ✅ **Алерты** настроены и отправляются
5. ✅ **Бэкапы** создаются автоматически
6. ✅ **DataLens** может подключаться к данным

### Следующие шаги

1. **Настройте DataLens** согласно инструкции в `dashboard-mvp/docs/DATALENS_CONNECTION_PLAN.md`
2. **Создайте дашборды** для визуализации данных
3. **Проведите обучение** пользователей работе с системой
4. **Настройте мониторинг** для отслеживания работоспособности

---

## КОНТАКТЫ ПОДДЕРЖКИ

- **Техническая поддержка**: [контакт разработчика]
- **Вопросы по DataLens**: [контакт специалиста по BI]
- **Экстренные случаи**: [экстренный контакт]

---

**Версия документа**: 1.0.0  
**Дата создания**: $(date +%Y-%m-%d)  
**Последнее обновление**: $(date +%Y-%m-%d)