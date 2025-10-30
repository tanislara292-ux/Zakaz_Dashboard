# ИСПРАВЛЕННАЯ ИНСТРУКЦИЯ ПО РАЗВЕРТЫВАНИЮ ZAKAZ DASHBOARD НА СЕРВЕРЕ ЗАКАЗЧИКА

## Обзор

Данная инструкция основана на анализе реальных проблем, возникших при развертывании на сервере заказчика (IP: 83.136.235.26). Инструкция включает исправления всех обнаруженных проблем и пошаговые команды для успешного развертывания.

## Выявленные проблемы

1. **Проблема с правами доступа Git**: `fatal: detected dubious ownership in repository`
2. **Проблема с правами доступа к директориям ClickHouse**: контейнер не может получить доступ к данным
3. **Проблема с файлом 00-admin.xml**: поврежденное содержимое с неверной кодировкой
4. **Проблема с паролями по умолчанию**: используются небезопасные пароли
5. **Проблема с пользователем etl**: отсутствуют права sudo для выполнения команд
6. **Проблема с healthcheck ClickHouse**: контейнер не становится здоровым

---

## ПОЛНАЯ ИНСТРУКЦИЯ РАЗВЕРТЫВАНИЯ

### ЭТАП 1: ПОДГОТОВКА СЕРВЕРА

#### 1.1 Подключение и базовая настройка

```bash
# Подключитесь к серверу по SSH
ssh root@83.136.235.26

# Обновите систему
apt update && apt upgrade -y

# Перезагрузите систему
reboot
```

#### 1.2 Установка Docker и Docker Compose

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version
```

#### 1.3 Создание пользователя ETL с правильными правами

```bash
# Создание пользователя etl
useradd -m -s /bin/bash etl

# Добавление в группы docker и sudo
usermod -aG docker etl
usermod -aG sudo etl

# Настройка безпарольного sudo для etl
printf 'etl ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-etl-nopasswd
chmod 440 /etc/sudoers.d/90-etl-nopasswd
```

#### 1.4 Установка дополнительных пакетов

```bash
# Установка необходимых утилит
apt install -y git curl wget htop unzip python3 python3-pip nano

# Установка Python зависимостей
pip3 install clickhouse-driver requests pandas python-dotenv
```

### ЭТАП 2: РАЗВЕРТЫВАНИЕ РЕПОЗИТОРИЯ

#### 2.1 Клонирование и настройка репозитория

```bash
# Создание директории для проекта
mkdir -p /opt/zakaz_dashboard
chown etl:etl /opt/zakaz_dashboard

# Переключение на пользователя etl
su - etl

# Клонирование репозитория
cd /opt/zakaz_dashboard
git clone https://github.com/tanislara292-ux/Zakaz_Dashboard.git .

# Переключение на последнюю стабильную ветку
git checkout main
git pull origin main
```

#### 2.2 Исправление проблемы с правами Git

```bash
# Если возникает ошибка "detected dubious ownership"
git config --global --add safe.directory /opt/zakaz_dashboard

# Проверка статуса
git status
```

### ЭТАП 3: НАСТРОЙКА CLICKHOUSE

#### 3.1 Подготовка конфигурации ClickHouse

```bash
# Переход в директорию ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse

# Копирование и настройка файла окружения
cp .env.example .env
nano .env
```

**Обязательно измените в файле .env:**
```bash
CLICKHOUSE_ADMIN_USER=admin
CLICKHOUSE_ADMIN_PASSWORD=ЗАМЕНИТЕ_НА_СИЛЬНЫЙ_ПАРОЛЬ
CLICKHOUSE_DB=zakaz
CLICKHOUSE_TZ=Europe/Moscow
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_NATIVE_PORT=9000
```

#### 3.2 Исправление файла 00-admin.xml

```bash
# Проверка и исправление файла 00-admin.xml
# Если файл содержит некорректные символы, замените его:

cat > users.d/00-admin.xml << 'EOF'
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
```

#### 3.3 Подготовка директорий и прав доступа

```bash
# Создание необходимых директорий
mkdir -p data logs user_files

# Установка правильных прав (важно для ClickHouse)
sudo chown -R 101:101 data logs user_files
chmod 755 data logs user_files
```

#### 3.4 Запуск ClickHouse

```bash
# Запуск ClickHouse через Docker Compose
docker-compose up -d

# Проверка статуса
docker-compose ps

# Проверка логов
docker-compose logs -f clickhouse
```

#### 3.5 Проверка работоспособности ClickHouse

```bash
# Ожидание запуска (может занять до 2 минут)
sleep 30

# Проверка healthcheck статуса
docker inspect -f '{{.State.Health.Status}}' ch-zakaz

# Если статус "unhealthy", проверьте логи:
docker logs ch-zakaz

# Проверка подключения
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SELECT 1"
```

### ЭТАП 4: ИНИЦИАЛИЗАЦИЯ СХЕМЫ БАЗЫ ДАННЫХ

#### 4.1 Применение схемы базы данных

```bash
# Возврат в корень проекта
cd /opt/zakaz_dashboard

# Применение схемы базы данных
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  < dashboard-mvp/infra/clickhouse/bootstrap_schema.sql

# Применение ролей и грантов
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  < dashboard-mvp/infra/clickhouse/bootstrap_roles_grants.sql
```

#### 4.2 Проверка создания таблиц

```bash
# Проверка таблиц в базе zakaz
docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  -q "SHOW TABLES FROM zakaz"

# Проверка прав пользователей
docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  -q "SHOW GRANTS FOR datalens_reader"
```

### ЭТАП 5: НАСТРОЙКА СЕКРЕТОВ И ТОКЕНОВ

#### 5.1 Создание директории для секретов

```bash
# Создание директории
mkdir -p /opt/zakaz_dashboard/secrets

# Установка прав доступа
chmod 700 /opt/zakaz_dashboard/secrets
chown etl:etl /opt/zakaz_dashboard/secrets
```

#### 5.2 Создание файла секретов QTickets API

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
DRY_RUN=false
```

#### 5.3 Создание файла секретов VK Ads

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

#### 5.4 Установка прав доступа к секретам

```bash
# Установка прав на файлы секретов
chmod 600 /opt/zakaz_dashboard/secrets/.env*
chown etl:etl /opt/zakaz_dashboard/secrets/.env*
```

### ЭТАП 6: СБОРКА DOCKER-ОБРАЗОВ

#### 6.1 Сборка образа QTickets API

```bash
# Переход в директорию проекта
cd /opt/zakaz_dashboard

# Сборка образа
docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# Проверка образа
docker images | grep qtickets_api
```

#### 6.2 Тестовый запуск QTickets API

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

### ЭТАП 7: НАСТРОЙКА SYSTEMD СЕРВИСОВ

#### 7.1 Копирование systemd юнитов

```bash
# Копирование файлов юнитов
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.service /etc/systemd/system/
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload
```

#### 7.2 Включение и запуск таймеров

```bash
# Включение таймеров
sudo systemctl enable --now qtickets_api.timer
sudo systemctl enable --now vk_ads.timer
sudo systemctl enable --now direct.timer

# Проверка статуса таймеров
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'
```

### ЭТАП 8: НАСТРОЙКА HTTPS ДОСТУПА

#### 8.1 Установка Caddy

```bash
# Установка Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy -y
```

#### 8.2 Настройка Caddyfile

```bash
# Создание Caddyfile
nano /etc/caddy/Caddyfile
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

# Healthcheck endpoint
bi.zakaz-dashboard.ru/healthz {
    respond "OK" 200
}
```

#### 8.3 Запуск Caddy

```bash
# Запуск Caddy
sudo systemctl enable --now caddy

# Проверка статуса
sudo systemctl status caddy

# Проверка HTTPS доступа
curl -k https://bi.zakaz-dashboard.ru/?query=SELECT%201
```

### ЭТАП 9: ПРОВЕРКА РАБОТОСПОСОБНОСТИ СИСТЕМЫ

#### 9.1 Запуск системной проверки

```bash
# Запуск скрипта проверки
cd /opt/zakaz_dashboard
bash dashboard-mvp/ops/system_check.sh
```

#### 9.2 Проверка данных в ClickHouse

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

---

## ТРАБЛШУТИНГ КОНКРЕТНЫХ ПРОБЛЕМ

### Проблема 1: ClickHouse не запускается

**Симптомы:**
- Контейнер не запускается
- Статус healthcheck: unhealthy
- Ошибки в логах

**Решение:**
```bash
# Проверка логов
docker logs ch-zakaz

# Проверка прав доступа к директориям
ls -la data logs

# Исправление прав
sudo chown -R 101:101 data logs

# Перезапуск
docker-compose restart
```

### Проблема 2: Ошибка "detected dubious ownership in repository"

**Решение:**
```bash
# Добавление директории в safe.directory
git config --global --add safe.directory /opt/zakaz_dashboard

# Или изменение владельца репозитория
sudo chown -R etl:etl /opt/zakaz_dashboard/.git
```

### Проблема 3: Файл 00-admin.xml поврежден

**Решение:**
```bash
# Полная замена файла
cat > users.d/00-admin.xml << 'EOF'
<?xml version="1.0"?>
<clickhouse>
  <users>
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

# Перезапуск ClickHouse
docker-compose restart
```

### Проблема 4: Пользователь etl не имеет прав sudo

**Решение:**
```bash
# Переключитесь на root
su -

# Добавление прав
usermod -aG sudo etl
printf 'etl ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-etl-nopasswd
chmod 440 /etc/sudoers.d/90-etl-nopasswd

# Переключитесь обратно на etl
su - etl
```

---

## ЧЕК-ЛИСТ ПЕРЕД ПЕРЕДАЧЕЙ ЗАКАЗЧИКУ

- [ ] **Сервер**: Ubuntu 24.04 с Docker и Docker Compose
- [ ] **Пользователь etl**: создан с правами sudo и docker
- [ ] **Git репозиторий**: склонирован и настроен
- [ ] **ClickHouse**: запущен и здоров (healthcheck: healthy)
- [ ] **Схема БД**: применена через bootstrap_schema.sql
- [ ] **Роли и гранты**: применены через bootstrap_roles_grants.sql
- [ ] **Секреты**: созданы с правильными правами (600)
- [ ] **Docker образы**: собраны и протестированы
- [ ] **Systemd сервисы**: настроены и запущены
- [ ] **HTTPS**: настроен через Caddy с SSL сертификатом
- [ ] **DataLens доступ**: проверен через HTTPS
- [ ] **Пароли**: изменены с значений по умолчанию
- [ ] **Бэкапы**: настроены и протестированы

---

## ПОЛЕЗНЫЕ КОМАНДЫ

### Проверка статуса системы
```bash
# Статус ClickHouse
docker-compose ps
docker logs ch-zakaz

# Статус таймеров
systemctl list-timers

# Статус сервисов
systemctl status qtickets_api.service
```

### Диагностика проблем
```bash
# Проверка дискового пространства
df -h

# Проверка использования памяти
free -h

# Проверка сетевых подключений
netstat -tlnp | grep -E '8123|9000|443'
```

### Работа с ClickHouse
```bash
# Подключение к CLI
docker exec -it ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ'

# Проверка таблиц
SHOW TABLES FROM zakaz;

# Проверка пользователей
SHOW USERS;

# Проверка грантов
SHOW GRANTS FOR datalens_reader;
```

---

## КОНТАКТЫ ПОДДЕРЖКИ

- **Техническая поддержка**: [контакт разработчика]
- **Экстренные случаи**: [экстренный контакт]
- **Документация**: [ссылка на документацию]

---

**Версия инструкции**: 1.0.0  
**Дата создания**: 2025-10-30  
**Последнее обновление**: 2025-10-30