# ФИНАЛЬНАЯ ИНСТРУКЦИЯ ПО РАЗВЕРТЫВАНИЮ ZAKAZ DASHBOARD НА СЕРВЕРЕ ЗАКАЗЧИКА

## Обзор

Данная инструкция представляет собой полный комплексный гид по развертыванию системы Zakaz Dashboard на сервере заказчика. Инструкция основана на анализе реальных проблем, возникших при развертывании на сервере заказчика (IP: 83.136.235.26), и включает все необходимые исправления и пошаговые команды.

### Содержание пакета развертывания

1. **[027_CUSTOMER_DEPLOYMENT_FIX.md](027_CUSTOMER_DEPLOYMENT_FIX.md)** - Исправленная инструкция по развертыванию
2. **[028_AUTOMATION_SCRIPTS.md](028_AUTOMATION_SCRIPTS.md)** - Автоматизационные скрипты для исправления проблем
3. **[029_PRE_DEPLOYMENT_CHECKLIST.md](029_PRE_DEPLOYMENT_CHECKLIST.md)** - Чек-лист перед развертыванием
4. **[030_SPECIFIC_TROUBLESHOOTING.md](030_SPECIFIC_TROUBLESHOOTING.md)** - Подробное руководство по решению проблем
5. **[021_UBUNTU_DEPLOYMENT_GUIDE.md](021_UBUNTU_DEPLOYMENT_GUIDE.md)** - Базовое руководство по развертыванию
6. **[024_COMPREHENSIVE_TROUBLESHOOTING_GUIDE.md](024_COMPREHENSIVE_TROUBLESHOOTING_GUIDE.md)** - Комплексное руководство по troubleshooting

---

## БЫСТРЫЙ СТАРТ (30 МИНУТ)

Если вам нужно быстро развернуть систему с минимальными проверками, следуйте этому сокращенному руководству.

### Шаг 1: Подготовка сервера (5 минут)

```bash
# Подключитесь к серверу по SSH
ssh root@83.136.235.26

# Обновите систему
apt update && apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Создание и настройка пользователя etl
useradd -m -s /bin/bash etl
usermod -aG docker etl
usermod -aG sudo etl
printf 'etl ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-etl-nopasswd
chmod 440 /etc/sudoers.d/90-etl-nopasswd
```

### Шаг 2: Развертывание репозитория (5 минут)

```bash
# Создание директории проекта
mkdir -p /opt/zakaz_dashboard
chown etl:etl /opt/zakaz_dashboard

# Переключение на пользователя etl
su - etl

# Клонирование репозитория
cd /opt/zakaz_dashboard
git clone https://github.com/tanislara292-ux/Zakaz_Dashboard.git .
git checkout main
git pull origin main

# Исправление проблем с Git
git config --global --add safe.directory /opt/zakaz_dashboard
```

### Шаг 3: Настройка ClickHouse (10 минут)

```bash
# Переход в директорию ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse

# Настройка конфигурации
cp .env.example .env
nano .env  # Изменить пароль администратора

# Создание директорий и прав доступа
mkdir -p data logs user_files
sudo chown -R 101:101 data logs user_files

# Запуск ClickHouse
docker-compose up -d

# Ожидание запуска (2-3 минуты)
sleep 30
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SELECT 1"
```

### Шаг 4: Применение схемы базы данных (5 минут)

```bash
# Возврат в корень проекта
cd /opt/zakaz_dashboard

# Применение схемы
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  < dashboard-mvp/infra/clickhouse/bootstrap_schema.sql

# Применение грантов
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  < dashboard-mvp/infra/clickhouse/bootstrap_roles_grants.sql
```

### Шаг 5: Настройка секретов (5 минут)

```bash
# Создание директории секретов
mkdir -p /opt/zakaz_dashboard/secrets
chmod 700 /opt/zakaz_dashboard/secrets

# Настройка QTickets API
nano /opt/zakaz_dashboard/secrets/.env.qtickets_api
```

Содержимое файла `.env.qtickets_api`:
```bash
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_TOKEN=ВАШ_БОЕВОЙ_ТОКЕН_QTICKETS
QTICKETS_SINCE_HOURS=24
ORG_NAME=zakaz
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=zakaz
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=EtL2024!Strong#Pass
TZ=Europe/Moscow
DRY_RUN=false
```

### Шаг 6: Сборка и запуск сервисов (5 минут)

```bash
# Сборка образа
cd /opt/zakaz_dashboard
docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# Настройка systemd юнитов
sudo cp dashboard-mvp/ops/systemd/*.service /etc/systemd/system/
sudo cp dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Запуск таймеров
sudo systemctl enable --now qtickets_api.timer
```

### Шаг 7: Настройка HTTPS (5 минут)

```bash
# Установка Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy -y

# Настройка Caddyfile
cat > /etc/caddy/Caddyfile << 'EOF'
bi.zakaz-dashboard.ru {
    reverse_proxy localhost:8123 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
}
EOF

# Запуск Caddy
systemctl enable --now caddy
```

---

## ПОЛНОЕ РАЗВЕРТЫВАНИЕ (2-3 ЧАСА)

Для полного развертывания с проверками и troubleshooting, следуйте подробной инструкции.

### Этап 1: Подготовка сервера

#### 1.1 Системные требования

Проверьте, что сервер соответствует требованиям:

- **CPU**: Минимум 4 ядра (рекомендуется 8+)
- **RAM**: Минимум 8GB (рекомендуется 16GB+)
- **Диск**: Минимум 100GB SSD (рекомендуется 500GB+)
- **ОС**: Ubuntu 20.04 LTS или новее
- **Сеть**: Стабильное интернет-соединение

#### 1.2 Обновление системы

```bash
# Подключитесь к серверу по SSH
ssh root@83.136.235.26

# Обновите систему
apt update && apt upgrade -y

# Перезагрузите систему
reboot
```

#### 1.3 Установка Docker и Docker Compose

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

#### 1.4 Установка дополнительных пакетов

```bash
# Установка необходимых утилит
apt install -y git curl wget htop unzip python3 python3-pip nano

# Установка Python зависимостей
pip3 install clickhouse-driver requests pandas python-dotenv
```

### Этап 2: Настройка пользователей и прав

#### 2.1 Создание пользователя ETL

```bash
# Создание пользователя для запуска ETL процессов
useradd -m -s /bin/bash etl

# Добавление в группы
usermod -aG docker etl
usermod -aG sudo etl

# Настройка безпарольного sudo
printf 'etl ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-etl-nopasswd
chmod 440 /etc/sudoers.d/90-etl-nopasswd
```

#### 2.2 Настройка файрвола

```bash
# Настройка UFW
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8123/tcp  # ClickHouse HTTP (только для локального доступа)
ufw enable
```

### Этап 3: Развертывание репозитория

#### 3.1 Клонирование и настройка

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

#### 3.2 Решение проблем с Git

```bash
# Если возникает ошибка "detected dubious ownership"
git config --global --add safe.directory /opt/zakaz_dashboard

# Проверка статуса
git status
```

### Этап 4: Настройка ClickHouse

#### 4.1 Подготовка конфигурации

```bash
# Переход в директорию ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse

# Копирование файла окружения
cp .env.example .env

# Редактирование конфигурации
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

#### 4.2 Исправление файла 00-admin.xml

```bash
# Проверка и исправление файла 00-admin.xml
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

#### 4.3 Подготовка директорий и прав доступа

```bash
# Создание необходимых директорий
mkdir -p data logs user_files

# Установка правильных прав (важно для ClickHouse)
sudo chown -R 101:101 data logs user_files
chmod 755 data logs user_files
```

#### 4.4 Запуск и проверка ClickHouse

```bash
# Запуск ClickHouse через Docker Compose
docker-compose up -d

# Проверка статуса
docker-compose ps

# Проверка логов
docker-compose logs -f clickhouse

# Ожидание запуска (может занять до 2 минут)
sleep 30

# Проверка healthcheck статуса
docker inspect -f '{{.State.Health.Status}}' ch-zakaz

# Проверка подключения
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SELECT 1"
```

### Этап 5: Инициализация схемы базы данных

#### 5.1 Применение схемы

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

#### 5.2 Проверка создания таблиц

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

### Этап 6: Настройка секретов и токенов

#### 6.1 Создание директории для секретов

```bash
# Создание директории
mkdir -p /opt/zakaz_dashboard/secrets

# Установка прав доступа
chmod 700 /opt/zakaz_dashboard/secrets
chown etl:etl /opt/zakaz_dashboard/secrets
```

#### 6.2 Настройка QTickets API

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

#### 6.3 Установка прав доступа к секретам

```bash
# Установка прав на файлы секретов
chmod 600 /opt/zakaz_dashboard/secrets/.env*
chown etl:etl /opt/zakaz_dashboard/secrets/.env*
```

### Этап 7: Сборка Docker-образов

#### 7.1 Сборка образа QTickets API

```bash
# Переход в директорию проекта
cd /opt/zakaz_dashboard

# Сборка образа
docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# Проверка образа
docker images | grep qtickets_api
```

#### 7.2 Тестовый запуск QTickets API

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

### Этап 8: Настройка systemd сервисов

#### 8.1 Установка systemd юнитов

```bash
# Копирование файлов юнитов
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.service /etc/systemd/system/
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload
```

#### 8.2 Включение и запуск таймеров

```bash
# Включение таймеров
sudo systemctl enable --now qtickets_api.timer
sudo systemctl enable --now vk_ads.timer
sudo systemctl enable --now direct.timer

# Проверка статуса таймеров
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'
```

### Этап 9: Настройка HTTPS доступа

#### 9.1 Установка Caddy

```bash
# Установка Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy -y
```

#### 9.2 Настройка Caddyfile

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

#### 9.3 Запуск Caddy

```bash
# Запуск Caddy
systemctl enable --now caddy

# Проверка статуса
systemctl status caddy

# Проверка HTTPS доступа
curl -k https://bi.zakaz-dashboard.ru/?query=SELECT%201
```

### Этап 10: Проверка работоспособности системы

#### 10.1 Запуск системной проверки

```bash
# Запуск скрипта проверки
cd /opt/zakaz_dashboard
bash dashboard-mvp/ops/system_check.sh
```

#### 10.2 Проверка данных в ClickHouse

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

#### 10.3 Проверка работы таймеров

```bash
# Проверка статуса таймеров
systemctl list-timers --all

# Проверка логов конкретного сервиса
journalctl -u qtickets_api.service --since "1 hour ago" -n 50
```

---

## АВТОМАТИЗАЦИЯ ИСПРАВЛЕНИЯ ПРОБЛЕМ

### Использование автоматизационных скриптов

Для автоматического исправления всех обнаруженных проблем используйте следующие скрипты:

#### 1. Комплексное исправление всех проблем

```bash
# Создание директории для скриптов
mkdir -p /opt/zakaz_dashboard/scripts

# Создание скриптов (содержание в файле 028_AUTOMATION_SCRIPTS.md)
# Скопируйте каждый скрипт в соответствующий файл

# Установка прав выполнения
chmod +x /opt/zakaz_dashboard/scripts/*.sh

# Запуск комплексного исправления
bash /opt/zakaz_dashboard/scripts/fix_all_deployment_issues.sh
```

#### 2. Проверка готовности к развертыванию

```bash
# Запуск проверки готовности
bash /opt/zakaz_dashboard/scripts/check_deployment_readiness.sh
```

#### 3. Индивидуальное исправление проблем

```bash
# Исправление прав Git
bash /opt/zakaz_dashboard/scripts/fix_git_permissions.sh

# Настройка пользователя etl
bash /opt/zakaz_dashboard/scripts/setup_etl_user.sh

# Восстановление 00-admin.xml
bash /opt/zakaz_dashboard/scripts/fix_admin_xml.sh

# Исправление прав ClickHouse
bash /opt/zakaz_dashboard/scripts/fix_clickhouse_permissions.sh

# Исправление контейнера ClickHouse
bash /opt/zakaz_dashboard/scripts/fix_clickhouse_container.sh

# Применение схемы и грантов
bash /opt/zakaz_dashboard/scripts/apply_clickhouse_schema.sh
```

---

## ТРАБЛШУТИНГ КОНКРЕТНЫХ ПРОБЛЕМ

### Быстрый поиск и решение проблем

Используйте это руководство для быстрого решения конкретных проблем:

1. **Ошибка "detected dubious ownership in repository"**:
   - Решение: `git config --global --add safe.directory /opt/zakaz_dashboard`
   - Или: `chown -R etl:etl /opt/zakaz_dashboard/.git`

2. **ClickHouse не запускается**:
   - Решение: `chown -R 101:101 data logs user_files`
   - Перезапуск: `docker-compose restart`

3. **Файл 00-admin.xml поврежден**:
   - Решение: Полная замена файла (см. раздел 4.2)

4. **Пользователь etl не имеет прав sudo**:
   - Решение: `usermod -aG sudo etl` и настройка `/etc/sudoers.d/90-etl-nopasswd`

5. **HTTPS не работает**:
   - Решение: Проверка конфигурации Caddy и файрвола

6. **Данные не загружаются из QTickets API**:
   - Решение: Проверка токена и конфигурации `.env.qtickets_api`

Подробные инструкции по каждой проблеме содержатся в файле [030_SPECIFIC_TROUBLESHOOTING.md](030_SPECIFIC_TROUBLESHOOTING.md).

---

## ЧЕК-ЛИСТ ПЕРЕД ПЕРЕДАЧЕЙ ЗАКАЗЧИКУ

### Финальная проверка

Перед передачей системы заказчику выполните следующие проверки:

#### Инфраструктура
- [ ] **Сервер**: Ubuntu 24.04 с 4+ CPU, 8GB+ RAM, 100GB+ SSD
- [ ] **Сеть**: Открыты порты 80, 443, настроен домен
- [ ] **Доступ**: SSH с правами sudo
- [ ] **Токены**: Получены API токены QTickets, VK Ads, Яндекс.Директ

#### Компоненты системы
- [ ] **Docker**: Установлен и работает
- [ ] **Docker Compose**: Установлен
- [ ] **Git**: Клонирован репозиторий
- [ ] **Права**: Настроены права доступа к директориям

#### ClickHouse
- [ ] **Конфигурация**: `.env` файл настроен
- [ ] **Контейнер**: Запущен и здоров
- [ ] **Схема**: Применена через `bootstrap_clickhouse.sh`
- [ ] **Пользователи**: Созданы admin, etl_writer, datalens_reader
- [ ] **Таблицы**: Созданы все необходимые таблицы

#### Секреты и токены
- [ ] **QTickets API**: `.env.qtickets_api` настроен
- [ ] **VK Ads**: `.env.vk` настроен
- [ ] **Яндекс.Директ**: `.env.direct` настроен
- [ ] **Права**: Файлы секретов имеют права 600

#### Сервисы
- [ ] **Docker образ**: qtickets_api собран
- [ ] **Тестовый запуск**: Dry-run работает корректно
- [ ] **Systemd юниты**: Скопированы и перезагружены
- [ ] **Таймеры**: Включены и работают по расписанию

#### HTTPS и доступность
- [ ] **Caddy**: Установлен и настроен
- [ ] **SSL сертификат**: Настроен для домена
- [ ] **HTTPS доступ**: ClickHouse доступен по HTTPS
- [ ] **Проверка**: `curl -k https://bi.zakaz-dashboard.ru/?query=SELECT%201` работает

#### DataLens
- [ ] **Подключение**: Создано и проверено
- [ ] **Источники**: Созданы все необходимые источники
- [ ] **Датасеты**: Настроены с правильными типами
- [ ] **Дашборды**: Созданы и отображают данные
- [ ] **Автообновление**: Настроено с интервалом 15 минут

#### Мониторинг
- [ ] **Алерты**: Настроены email уведомления
- [ ] **Логирование**: Настроено ротация логов
- [ ] **Бэкапы**: Настроены автоматические бэкапы
- [ ] **Проверки**: Настроены ежедневные проверки

---

## ПОДКЛЮЧЕНИЕ К YANDEX DATALENS

### Параметры подключения

- **Хост**: `bi.zakaz-dashboard.ru`
- **Порт**: `443`
- **База данных**: `zakaz`
- **Имя пользователя**: `datalens_reader`
- **Пароль**: `ChangeMe123!`
- **Использовать HTTPS**: ✅

### SQL-запросы для DataLens

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
systemctl restart qtickets_api.service

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

1. **Настройте DataLens** согласно инструкции в `023_DATALENS_SETUP_GUIDE.md`
2. **Создайте дашборды** для визуализации данных
3. **Проведите обучение** пользователей работе с системой
4. **Настройте мониторинг** для отслеживания работоспособности

---

## КОНТАКТЫ ПОДДЕРЖКИ

- **Техническая поддержка**: [контакт разработчика]
- **Вопросы по DataLens**: [контакт специалиста по BI]
- **Экстренные случаи**: [экстренный контакт]

---

## ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

### Документация

- **Основное руководство**: [021_UBUNTU_DEPLOYMENT_GUIDE.md](021_UBUNTU_DEPLOYMENT_GUIDE.md)
- **Исправленная инструкция**: [027_CUSTOMER_DEPLOYMENT_FIX.md](027_CUSTOMER_DEPLOYMENT_FIX.md)
- **Автоматизационные скрипты**: [028_AUTOMATION_SCRIPTS.md](028_AUTOMATION_SCRIPTS.md)
- **Чек-лист**: [029_PRE_DEPLOYMENT_CHECKLIST.md](029_PRE_DEPLOYMENT_CHECKLIST.md)
- **Troubleshooting**: [030_SPECIFIC_TROUBLESHOOTING.md](030_SPECIFIC_TROUBLESHOOTING.md)
- **Комплексный troubleshooting**: [024_COMPREHENSIVE_TROUBLESHOOTING_GUIDE.md](024_COMPREHENSIVE_TROUBLESHOOTING_GUIDE.md)

### SQL-запросы для DataLens

```sql
-- Основные продажи
SELECT 
    event_date,
    city,
    event_name,
    tickets_sold,
    revenue,
    (revenue - refunds_amount) AS net_revenue
FROM zakaz.v_qtickets_sales_latest
WHERE event_date >= today() - INTERVAL 30 DAY

-- Маркетинговые данные
SELECT 
    d AS event_date,
    city,
    spend_total,
    net_revenue,
    romi
FROM zakaz.v_marketing_daily
WHERE d >= today() - INTERVAL 30 DAY

-- Свежесть данных
SELECT 
    source,
    table_name,
    latest_date,
    days_behind
FROM zakaz.v_qtickets_freshness
```

---

**Версия документа**: 1.0.0  
**Дата создания**: 2025-10-30  
**Последнее обновление**: 2025-10-30

---

*Этот документ предоставляет полную инструкцию по развертыванию системы Zakaz Dashboard на сервере заказчика с учетом всех обнаруженных проблем и их решений. При возникновении вопросов обращайтесь к подробным руководствам или в службу поддержки.*