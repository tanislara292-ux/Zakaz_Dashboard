# ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ ПРОБЛЕМ РАЗВЕРТЫВАНИЯ

## Обзор

Данное руководство предназначено для немедленного исправления конкретных проблем, возникших при развертывании на сервере заказчика (IP: 83.136.235.26). Основная проблема - некорректный файл 00-admin.xml, который вызывает ошибки парсинга XML в ClickHouse.

---

## СРОЧНОЕ ИСПРАВЛЕНИЕ (5 МИНУТ)

### Шаг 1: Исправление файла 00-admin.xml (1 минута)

```bash
# Переключитесь в директорию ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d

# Создание резервной копии
cp 00-admin.xml 00-admin.xml.backup.$(date +%Y%m%d_%H%M%S)

# Полная замена файла с корректным содержимым
cat > 00-admin.xml << 'EOF'
<?xml version="1.0"?>
<clickhouse>
  <!-- Primary administrator with full access -->
  <users>
    <!-- Remove the built-in default account -->
    <default remove="1"/>
    
    <admin>
      <password><![CDATA[admin_pass]]></password>
      <networks>
        <ip>::/0</ip>
      </networks>
      <profile>admin_profile</profile>
      <quota>default</quota>
      <access_management>1</access_management>
      <grants>
        <query>GRANT ALL ON *.* TO admin WITH GRANT OPTION</query>
      </grants>
    </admin>
  </users>
</clickhouse>
EOF

# Проверка синтаксиса
xmllint --noout 00-admin.xml && echo "XML синтаксис корректен" || echo "Ошибка в XML синтаксисе"
```

### Шаг 2: Перезапуск ClickHouse (2 минуты)

```bash
# Возврат в директорию ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse

# Полная остановка и очистка
docker-compose down
docker system prune -f

# Запуск
docker-compose up -d

# Ожидание запуска
sleep 30

# Проверка статуса
docker inspect -f '{{.State.Health.Status}}' ch-zakaz
```

### Шаг 3: Проверка подключения (1 минута)

```bash
# Проверка подключения к ClickHouse
docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "SELECT 1"

# Если подключение успешно, продолжаем
if [ $? -eq 0 ]; then
    echo "✅ ClickHouse работает корректно"
else
    echo "❌ Проблема с подключением к ClickHouse"
    docker logs ch-zakaz --tail 50
fi
```

---

## ПОЛНОЕ ИСПРАВЛЕНИЕ ЕСЛИ ПРОБЛЕМЫ ОСТАЮТСЯ

### Шаг 1: Диагностика проблем

```bash
# Проверка файла 00-admin.xml
file /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/00-admin.xml

# Проверка логов ClickHouse
docker logs ch-zakaz --tail 100

# Проверка конфигурации
cat /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/.env
```

### Шаг 2: Исправление прав доступа

```bash
# Исправление прав на директории
sudo chown -R 101:101 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/data
sudo chown -R 101:101 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/logs
sudo chown -R 101:101 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/user_files

# Установка прав доступа
sudo chmod 755 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/data
sudo chmod 755 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/logs
sudo chmod 755 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/user_files
```

### Шаг 3: Полная переустановка ClickHouse

```bash
# Остановка всех контейнеров
docker-compose down

# Удаление всех образов и томов
docker system prune -af --volumes

# Удаление проблемных файлов
rm -f /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/00-admin.xml

# Перезапуск с нуля
docker-compose up -d

# Ожидание запуска
sleep 60

# Проверка
docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "SELECT 1"
```

---

## ПРОВЕРКА РАБОТОСПОСОБНОСТИ

### Шаг 1: Проверка ClickHouse

```bash
# Проверка статуса контейнера
docker ps | grep ch-zakaz

# Проверка healthcheck
docker inspect -f '{{.State.Health.Status}}' ch-zakaz

# Проверка подключения
docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "SELECT 'ClickHouse OK' as status"
```

### Шаг 2: Применение схемы

```bash
# Применение схемы базы данных
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='admin_pass' \
  < /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/bootstrap_schema.sql

# Применение грантов
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='admin_pass' \
  < /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/bootstrap_roles_grants.sql

# Проверка таблиц
docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "SHOW TABLES FROM zakaz"
```

### Шаг 3: Настройка QTickets API

```bash
# Создание файла секретов
mkdir -p /opt/zakaz_dashboard/secrets
chmod 700 /opt/zakaz_dashboard/secrets

# Настройка QTickets API
cat > /opt/zakaz_dashboard/secrets/.env.qtickets_api << 'EOF'
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_TOKEN=ВАШ_БОЕВОЙ_ТОКЕН_QTICKETS
QTICKETS_SINCE_HOURS=24
ORG_NAME=zakaz
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=EtL2024!Strong#Pass
CLICKHOUSE_DATABASE=zakaz
TZ=Europe/Moscow
REPORT_TZ=Europe/Moscow
JOB_NAME=qtickets_api
DRY_RUN=false
EOF

# Установка прав
chmod 600 /opt/zakaz_dashboard/secrets/.env.qtickets_api
chown etl:etl /opt/zakaz_dashboard/secrets/.env.qtickets_api
```

---

## ЗАПУСК СЕРВИСОВ

### Шаг 1: Сборка образа QTickets API

```bash
# Сборка образа
cd /opt/zakaz_dashboard
docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# Проверка образа
docker images | grep qtickets_api
```

### Шаг 2: Настройка systemd

```bash
# Копирование файлов юнитов
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.service /etc/systemd/system/
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение таймеров
sudo systemctl enable --now qtickets_api.timer
```

---

## ТЕСТОВЫЙ ЗАПУСК

### Шаг 1: Тестовый запуск QTickets API

```bash
# Запуск в режиме dry-run
docker run --rm \
  --name qtickets_api_test \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run

# Проверка логов
docker logs qtickets_api_test
```

### Шаг 2: Проверка данных

```bash
# Проверка загрузки данных (через 15 минут)
sleep 15

# Проверка наличия данных
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader \
  --password='ChangeMe123!' \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_orders_raw WHERE sale_ts >= today() - INTERVAL 1 DAY"
```

---

## НАСТРОЙКА HTTPS

### Шаг 1: Установка Caddy

```bash
# Установка Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy -y
```

### Шаг 2: Настройка Caddyfile

```bash
# Создание Caddyfile
cat > /etc/caddy/Caddyfile << 'EOF'
bi.zakaz-dashboard.ru {
    reverse_proxy localhost:8123 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
    
    # Healthcheck endpoint
    /healthz {
        respond "OK" 200
    }
}
EOF

# Запуск Caddy
systemctl enable --now caddy
```

---

## ФИНАЛЬНАЯ ПРОВЕРКА

### Комплексная проверка

```bash
# Проверка всех компонентов
echo "=== ФИНАЛЬНАЯ ПРОВЕРКА ==="
echo "1. ClickHouse:"
docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "SELECT 'ClickHouse OK'"

echo "2. Таблицы:"
docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "SHOW TABLES FROM zakaz"

echo "3. QTickets API:"
systemctl status qtickets_api.timer

echo "4. HTTPS:"
curl -k https://bi.zakaz-dashboard.ru/healthz

echo "5. Данные:"
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader \
  --password='ChangeMe123!' \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_orders_raw"
```

---

## КОНТАКТЫ ПОДДЕРЖКИ

- **Техническая поддержка**: [контакт разработчика]
- **Экстренные случаи**: [экстренный контакт]

---

**Версия инструкции**: 1.0.0  
**Дата создания**: 2025-10-30  
**Последнее обновление**: 2025-10-30

---

*Эта инструкция предоставляет экстренное исправление проблем развертывания. После выполнения всех шагов система должна работать корректно.*