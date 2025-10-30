# ПОДРОБНОЕ РУКОВОДСТВО ПО РЕШЕНИЮ КОНКРЕТНЫХ ПРОБЛЕМ РАЗВЕРТЫВАНИЯ

## Обзор

Данное руководство содержит подробные инструкции по решению конкретных проблем, обнаруженных при развертывании на сервере заказчика (IP: 83.136.235.26). Каждая проблема включает диагностику, пошаговое решение и проверку результата.

---

## ПРОБЛЕМА 1: ОШИБКА "DETECTED DUBIOUS OWNERSHIP IN REPOSITORY"

### Симптомы

```
fatal: detected dubious ownership in repository at '/opt/zakaz_dashboard'
To add an exception for this directory, call:
        git config --global --add safe.directory /opt/zakaz_dashboard
```

### Причина

Git 2.35+ ввел новую функцию безопасности, которая предотвращает выполнение команд в репозиториях, принадлежащих другому пользователю.

### Диагностика

```bash
# Проверка текущего пользователя
whoami

# Проверка владельца директории
ls -ld /opt/zakaz_dashboard

# Проверка владельца .git
ls -ld /opt/zakaz_dashboard/.git

# Попытка выполнения Git команды
cd /opt/zakaz_dashboard && git status
```

### Решение 1: Изменение владельца репозитория

```bash
# Переключитесь на root
sudo su -

# Изменение владельца репозитория
chown -R etl:etl /opt/zakaz_dashboard

# Проверка результата
ls -ld /opt/zakaz_dashboard
```

### Решение 2: Добавление в safe.directory

```bash
# Переключитесь на пользователя, от имени которого будет выполняться Git
su - etl

# Добавление директории в safe.directory
git config --global --add safe.directory /opt/zakaz_dashboard

# Проверка результата
git config --global --get safe.directory
```

### Решение 3: Комбинированный подход

```bash
# От root
sudo su -

# Изменение владельца .git
chown -R etl:etl /opt/zakaz_dashboard/.git

# Переключение на etl
su - etl

# Добавление в safe.directory
git config --global --add safe.directory /opt/zakaz_dashboard

# Проверка
git status
```

### Проверка результата

```bash
# Выполнение Git команды без ошибок
cd /opt/zakaz_dashboard
git status
git fetch --all
git checkout main
```

---

## ПРОБЛЕМА 2: CLICKHOUSE КОНТЕЙНЕР НЕ ЗАПУСКАЕТСЯ

### Симптомы

```
Container ch-zakaz is restarting
Healthcheck status: unhealthy
Error: Code: 210. DB::NetException: Connection refused (localhost:9000)
```

### Причина

Неправильные права доступа к директориям данных ClickHouse или неверная конфигурация.

### Диагностика

```bash
# Проверка статуса контейнера
docker ps -a | grep ch-zakaz

# Проверка логов контейнера
docker logs ch-zakaz

# Проверка прав доступа к директориям
ls -la /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/data
ls -la /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/logs

# Проверка конфигурации
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
cat .env
```

### Решение 1: Исправление прав доступа

```bash
# Переключитесь на root
sudo su -

# Создание необходимых директорий
mkdir -p /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/data
mkdir -p /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/logs
mkdir -p /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/user_files

# Установка правильных прав (101:101 - пользователь ClickHouse в контейнере)
chown -R 101:101 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/data
chown -R 101:101 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/logs
chown -R 101:101 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/user_files

# Установка прав доступа
chmod 755 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/data
chmod 755 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/logs
chmod 755 /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/user_files
```

### Решение 2: Проверка конфигурации .env

```bash
# Переход в директорию ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse

# Проверка содержимого .env
cat .env

# Если файл отсутствует или некорректен:
cp .env.example .env
nano .env

# Убедитесь, что переменные установлены:
CLICKHOUSE_ADMIN_USER=admin
CLICKHOUSE_ADMIN_PASSWORD=ВАШ_ПАРОЛЬ
CLICKHOUSE_DB=zakaz
CLICKHOUSE_TZ=Europe/Moscow
```

### Решение 3: Полный перезапуск

```bash
# Остановка контейнера
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
docker-compose down

# Очистка (опционально)
docker system prune -f

# Запуск
docker-compose up -d

# Проверка логов
docker-compose logs -f clickhouse
```

### Проверка результата

```bash
# Проверка статуса
docker ps | grep ch-zakaz

# Проверка healthcheck
docker inspect -f '{{.State.Health.Status}}' ch-zakaz

# Проверка подключения
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SELECT 1"
```

---

## ПРОБЛЕМА 3: ПОВРЕЖДЕННЫЙ ФАЙЛ 00-ADMIN.XML

### Симптомы

```
Error: XML syntax error in users.d/00-admin.xml
ClickHouse container fails to start
File contains corrupted characters
```

### Причина

Файл 00-admin.xml поврежден или содержит некорректные символы кодировки.

### Диагностика

```bash
# Проверка файла
cat /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/00-admin.xml

# Проверка синтаксиса XML
xmllint --noout /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/00-admin.xml

# Проверка кодировки
file /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d/00-admin.xml
```

### Решение: Полная замена файла

```bash
# Переход в директорию
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse/users.d

# Создание резервной копии
cp 00-admin.xml 00-admin.xml.backup.$(date +%Y%m%d_%H%M%S)

# Создание нового файла с корректным содержимым
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
xmllint --noout 00-admin.xml

# Установка прав
chown etl:etl 00-admin.xml
chmod 644 00-admin.xml
```

### Проверка результата

```bash
# Проверка синтаксиса
xmllint --noout 00-admin.xml

# Проверка содержимого
cat 00-admin.xml

# Перезапуск ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
docker-compose restart

# Проверка логов
docker-compose logs clickhouse
```

---

## ПРОБЛЕМА 4: ПОЛЬЗОВАТЕЛЬ ETL НЕ ИМЕЕТ ПРАВ SUDO

### Симптомы

```
sudo: a password is required for etl
Permission denied
Failed to start service
```

### Причина

Пользователь etl не настроен правильно или отсутствуют права sudo.

### Диагностика

```bash
# Проверка текущего пользователя
whoami

# Проверка пользователя etl
id etl

# Проверка групп пользователя
groups etl

# Проверка прав sudo
sudo -u etl sudo -n true
```

### Решение 1: Настройка пользователя etl

```bash
# Переключитесь на root
sudo su -

# Создание пользователя (если не существует)
useradd -m -s /bin/bash etl

# Добавление в группы
usermod -aG docker etl
usermod -aG sudo etl

# Настройка безпарольного sudo
printf 'etl ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-etl-nopasswd
chmod 440 /etc/sudoers.d/90-etl-nopasswd
```

### Решение 2: Проверка и исправление существующего пользователя

```bash
# Переключитесь на root
sudo su -

# Проверка пользователя
id etl

# Добавление в группы (если отсутствуют)
usermod -aG docker etl
usermod -aG sudo etl

# Настройка sudoers
printf 'etl ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-etl-nopasswd
chmod 440 /etc/sudoers.d/90-etl-nopasswd

# Проверка
visudo -c
```

### Проверка результата

```bash
# Переключитесь на etl
su - etl

# Проверка пользователя
id
groups

# Проверка sudo
sudo whoami
sudo -n true

# Проверка доступа к Docker
docker ps
```

---

## ПРОБЛЕМА 5: НЕ ПРИМЕНЯЮТСЯ ГРАНТЫ CLICKHOUSE

### Симптомы

```
Access denied for user datalens_reader
Error: Permission denied
GRANT statements fail
```

### Причина

Гранты не применены или пользователь не существует.

### Диагностика

```bash
# Подключение к ClickHouse
docker exec -it ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ'

# Проверка пользователей
SHOW USERS;

# Проверка грантов
SHOW GRANTS FOR datalens_reader;

# Проверка ролей
SHOW ROLES;
```

### Решение 1: Применение грантов

```bash
# Переход в директорию проекта
cd /opt/zakaz_dashboard

# Применение ролей и грантов
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  < dashboard-mvp/infra/clickhouse/bootstrap_roles_grants.sql
```

### Решение 2: Ручное применение грантов

```bash
# Подключение к ClickHouse
docker exec -it ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ'

# Создание ролей
CREATE ROLE IF NOT EXISTS role_bi_reader;
CREATE ROLE IF NOT EXISTS role_etl_writer;
CREATE ROLE IF NOT EXISTS role_backup_operator;

# Предоставление грантов ролям
GRANT SELECT ON zakaz.* TO role_bi_reader;
GRANT SELECT ON meta.* TO role_bi_reader;
GRANT SELECT ON bi.* TO role_bi_reader;
GRANT SELECT ON system.query_log TO role_bi_reader;
GRANT SELECT ON system.part_log TO role_bi_reader;
GRANT SELECT ON system.tables TO role_bi_reader;
GRANT SELECT ON system.databases TO role_bi_reader;

GRANT SELECT, INSERT ON zakaz.* TO role_etl_writer;
GRANT SELECT ON meta.* TO role_etl_writer;

GRANT SELECT ON zakaz.* TO role_backup_operator;
GRANT SELECT, INSERT ON meta.backup_runs TO role_backup_operator;

# Назначение ролей пользователям
GRANT role_bi_reader TO datalens_reader;
GRANT role_etl_writer TO etl_writer;
GRANT role_backup_operator TO backup_user;
```

### Проверка результата

```bash
# Подключение к ClickHouse
docker exec -it ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ'

# Проверка грантов
SHOW GRANTS FOR datalens_reader;
SHOW GRANTS FOR etl_writer;

# Тест подключения от datalens_reader
docker exec -it ch-zakaz clickhouse-client --user=datalens_reader --password='ChangeMe123!' -q "SELECT 1"
```

---

## ПРОБЛЕМА 6: НЕ РАБОТАЕТ HTTPS ДОСТУП ЧЕРЕЗ CADDY

### Симптомы

```
HTTPS connection refused
SSL certificate error
502 Bad Gateway
```

### Причина

Неправильная конфигурация Caddy или проблемы с сетью.

### Диагностика

```bash
# Проверка статуса Caddy
systemctl status caddy

# Проверка логов Caddy
journalctl -u caddy -n 50

# Проверка конфигурации
caddy validate --config /etc/caddy/Caddyfile

# Проверка сетевых портов
netstat -tlnp | grep -E '80|443|8123'

# Проверка DNS
nslookup bi.zakaz-dashboard.ru
```

### Решение 1: Настройка Caddyfile

```bash
# Проверка существования Caddyfile
ls -la /etc/caddy/Caddyfile

# Создание правильного Caddyfile
cat > /etc/caddy/Caddyfile << 'EOF'
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
EOF

# Проверка конфигурации
caddy validate --config /etc/caddy/Caddyfile
```

### Решение 2: Перезапуск Caddy

```bash
# Перезапуск Caddy
systemctl restart caddy

# Проверка статуса
systemctl status caddy

# Проверка логов
journalctl -u caddy -f
```

### Решение 3: Проверка файрвола

```bash
# Проверка статуса UFW
ufw status

# Открытие портов (если закрыты)
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8123/tcp

# Перезагрузка файрвола
ufw reload
```

### Проверка результата

```bash
# Проверка HTTP
curl -I http://bi.zakaz-dashboard.ru/

# Проверка HTTPS
curl -k -I https://bi.zakaz-dashboard.ru/

# Проверка ClickHouse через HTTPS
curl -k https://bi.zakaz-dashboard.ru/?query=SELECT%201
```

---

## ПРОБЛЕМА 7: НЕ ЗАГРУЖАЮТСЯ ДАННЫЕ ИЗ QTICKETS API

### Симптомы

```
No data in stg_qtickets_api_orders_raw
QTickets API connection failed
Authentication error
```

### Причина

Неправильная конфигурация токена или проблемы с доступом к API.

### Диагностика

```bash
# Проверка файла конфигурации
cat /opt/zakaz_dashboard/secrets/.env.qtickets_api

# Проверка токена
curl -H "Authorization: Bearer ВАШ_ТОКЕН" \
     -H "Accept: application/json" \
     "https://qtickets.ru/api/rest/v1/orders?limit=1"

# Проверка логов сервиса
journalctl -u qtickets_api.service -n 50

# Ручной запуск для отладки
docker run --rm \
  --name qtickets_debug \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run --log-level DEBUG
```

### Решение 1: Проверка и обновление токена

```bash
# Редактирование файла конфигурации
nano /opt/zakaz_dashboard/secrets/.env.qtickets_api

# Проверка токена
QTICKETS_TOKEN="ВАШ_НОВЫЙ_ТОКЕН"

# Проверка доступа
curl -H "Authorization: Bearer $QTICKETS_TOKEN" \
     -H "Accept: application/json" \
     "https://qtickets.ru/api/rest/v1/orders?limit=1"
```

### Решение 2: Проверка конфигурации ClickHouse

```bash
# Проверка параметров подключения
grep -E "CLICKHOUSE_HOST|CLICKHOUSE_PORT|CLICKHOUSE_USER|CLICKHOUSE_PASSWORD" /opt/zakaz_dashboard/secrets/.env.qtickets_api

# Тест подключения к ClickHouse
docker exec ch-zakaz clickhouse-client \
  --user=etl_writer \
  --password='EtL2024!Strong#Pass' \
  -q "SELECT 1"
```

### Решение 3: Перезапуск сервиса

```bash
# Перезапуск сервиса
systemctl restart qtickets_api.service

# Проверка статуса
systemctl status qtickets_api.service

# Проверка логов
journalctl -u qtickets_api.service -f
```

### Проверка результата

```bash
# Проверка данных в ClickHouse
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader \
  --password='ChangeMe123!' \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_orders_raw WHERE sale_ts >= today() - INTERVAL 1 DAY"

# Проверка свежести данных
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader \
  --password='ChangeMe123!' \
  -q "SELECT max(sale_ts) FROM zakaz.stg_qtickets_api_orders_raw"
```

---

## ПРОБЛЕМА 8: НЕ РАБОТАЮТ ТАЙМЕРЫ SYSTEMD

### Симптомы

```
Timer not found
Service failed to start
No next execution time
```

### Причина

Неправильная конфигурация юнитов systemd или отсутствие прав.

### Диагностика

```bash
# Проверка статуса таймеров
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'

# Проверка статуса сервисов
systemctl status qtickets_api.service
systemctl status vk_ads.service
systemctl status direct.service

# Проверка файлов юнитов
ls -la /etc/systemd/system/ | grep -E 'qtickets|vk_ads|direct'
```

### Решение 1: Копирование файлов юнитов

```bash
# Копирование файлов сервисов
cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.service /etc/systemd/system/

# Копирование файлов таймеров
cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/

# Перезагрузка systemd
systemctl daemon-reload
```

### Решение 2: Включение и запуск таймеров

```bash
# Включение таймеров
systemctl enable qtickets_api.timer
systemctl enable vk_ads.timer
systemctl enable direct.timer

# Запуск таймеров
systemctl start qtickets_api.timer
systemctl start vk_ads.timer
systemctl start direct.timer

# Проверка статуса
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'
```

### Решение 3: Проверка конфигурации юнитов

```bash
# Проверка файла сервиса
cat /etc/systemd/system/qtickets_api.service

# Проверка файла таймера
cat /etc/systemd/system/qtickets_api.timer

# Исправление путей (если необходимо)
nano /etc/systemd/system/qtickets_api.service
```

### Проверка результата

```bash
# Проверка таймеров
systemctl list-timers --all

# Проверка следующего запуска
systemctl list-timers | grep qtickets_api

# Проверка логов
journalctl -u qtickets_api.service --since "1 hour ago"
```

---

## ОБЩИЙ ПОДХОД К РЕШЕНИЮ ПРОБЛЕМ

### Алгоритм диагностики

1. **Сбор информации**:
   - Проверка логов всех компонентов
   - Проверка статуса сервисов
   - Проверка конфигурационных файлов

2. **Изоляция проблемы**:
   - Определение компонента с проблемой
   - Проверка зависимостей
   - Воспроизведение проблемы

3. **Применение решения**:
   - Использование соответствующего скрипта
   - Пошаговое выполнение исправлений
   - Проверка каждого шага

4. **Верификация**:
   - Проверка работоспособности
   - Тестирование функциональности
   - Мониторинг стабильности

### Автоматизация

Для автоматического исправления всех проблем используйте:

```bash
# Запуск комплексного исправления
bash /opt/zakaz_dashboard/scripts/fix_all_deployment_issues.sh

# Проверка результата
bash /opt/zakaz_dashboard/scripts/check_deployment_readiness.sh
```

---

## КОНТАКТЫ ПОДДЕРЖКИ

- **Техническая поддержка**: [контакт разработчика]
- **Экстренные случаи**: [экстренный контакт]
- **Документация**: [ссылка на документацию]

---

**Версия руководства**: 1.0.0  
**Дата создания**: 2025-10-30  
**Последнее обновление**: 2025-10-30