# ИНСТРУКЦИЯ ПО РАЗВЕРТЫВАНИЮ НА ЧИСТОМ СЕРВЕРЕ

## Обзор

Данная инструкция описывает самый надежный способ развертывания Zakaz Dashboard на чистом сервере заказчика. Этот подход позволяет избежать всех проблем, возникших при попытке развертывания на уже настроенном сервере.

---

## ПРЕИМУЩЕСТВА ЧИСТОГО СЕРВЕРА

1. **Нет конфликтов** с существующими конфигурациями
2. **Минимум проблем** с правами доступа
3. **Чистая среда** без остаточных файлов
4. **Быстрое развертывание** (30-40 минут)
5. **Гарантированная работоспособность** всех компонентов

---

## ПОДГОТОВКА К ЧИСТОМУ РАЗВЕРТЫВАНИЮ

### Шаг 1: Подготовка сервера заказчика

```bash
# 1.1. Создание резервной копии существующих данных (если необходимо)
ssh root@83.136.235.26
mkdir -p /root/backup_$(date +%Y%m%d)
cp -r /opt/zakaz_dashboard /root/backup_$(date +%Y%m%d)/ 2>/dev/null || true

# 1.2. Очистка существующей установки (если была)
rm -rf /opt/zakaz_dashboard
userdel -r etl 2>/dev/null || true
docker system prune -af
docker volume prune -f
```

### Шаг 2: Подготовка чистового сервера

```bash
# 2.1. Обновление системы
apt update && apt upgrade -y

# 2.2. Установка необходимых пакетов
apt install -y git curl wget htop unzip python3 python3-pip nano

# 2.3. Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 2.4. Установка Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 2.5. Проверка установки
docker --version
docker-compose --version
```

---

## ПОЛНОЕ РАЗВЕРТЫВАНИЕ НА ЧИСТОМ СЕРВЕРЕ (40 МИНУТ)

### Этап 1: Создание пользователя и структуры (5 минут)

```bash
# 1.1. Создание пользователя etl
useradd -m -s /bin/bash etl

# 1.2. Добавление в группы
usermod -aG docker etl
usermod -aG sudo etl

# 1.3. Настройка безпарольного sudo
printf 'etl ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-etl-nopasswd
chmod 440 /etc/sudoers.d/90-etl-nopasswd

# 1.4. Создание директории проекта
mkdir -p /opt/zakaz_dashboard
chown etl:etl /opt/zakaz_dashboard
```

### Этап 2: Клонирование и настройка репозитория (5 минут)

```bash
# 2.1. Переключение на пользователя etl
su - etl

# 2.2. Клонирование репозитория
cd /opt/zakaz_dashboard
git clone https://github.com/tanislara292-ux/Zakaz_Dashboard.git .

# 2.3. Переключение на стабильную ветку
git checkout main
git pull origin main

# 2.4. Настройка Git (если необходимо)
git config --global --add safe.directory /opt/zakaz_dashboard
```

### Этап 3: Настройка ClickHouse (10 минут)

```bash
# 3.1. Переход в директорию ClickHouse
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse

# 3.2. Создание конфигурации
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

```bash
# 3.3. Создание директорий и прав доступа
mkdir -p data logs user_files
sudo chown -R 101:101 data logs user_files
chmod 755 data logs user_files

# 3.4. Запуск ClickHouse
docker-compose up -d

# 3.5. Ожидание запуска (2-3 минуты)
sleep 30
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SELECT 1"
```

### Этап 4: Инициализация базы данных (5 минут)

```bash
# 4.1. Возврат в корень проекта
cd /opt/zakaz_dashboard

# 4.2. Применение схемы
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  < dashboard-mvp/infra/clickhouse/bootstrap_schema.sql

# 4.3. Применение грантов
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  < dashboard-mvp/infra/clickhouse/bootstrap_roles_grants.sql

# 4.4. Проверка результата
docker exec ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  -q "SHOW TABLES FROM zakaz"
```

### Этап 5: Настройка секретов (5 минут)

```bash
# 5.1. Создание директории секретов
mkdir -p /opt/zakaz_dashboard/secrets
chmod 700 /opt/zakaz_dashboard/secrets

# 5.2. Настройка QTickets API
nano /opt/zakaz_dashboard/secrets/.env.qtickets_api
```

Содержимое файла `.env.qtickets_api`:
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

```bash
# 5.3. Установка прав доступа
chmod 600 /opt/zakaz_dashboard/secrets/.env*
chown etl:etl /opt/zakaz_dashboard/secrets/.env*
```

### Этап 6: Сборка и тестирование Docker-образов (5 минут)

```bash
# 6.1. Сборка образа QTickets API
cd /opt/zakaz_dashboard
docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# 6.2. Тестовый запуск
docker run --rm \
  --name qtickets_api_test \
  --env-file /opt/zakaz_dashboard/secrets/.env.qtickets_api \
  qtickets_api:latest \
  --since-hours 24 --dry-run

# 6.3. Проверка логов
docker logs qtickets_api_test
```

### Этап 7: Настройка systemd сервисов (5 минут)

```bash
# 7.1. Копирование файлов юнитов
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.service /etc/systemd/system/
sudo cp /opt/zakaz_dashboard/dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/

# 7.2. Перезагрузка systemd
sudo systemctl daemon-reload

# 7.3. Включение таймеров
sudo systemctl enable --now qtickets_api.timer
sudo systemctl enable --now vk_ads.timer
sudo systemctl enable --now direct.timer

# 7.4. Проверка статуса
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'
```

### Этап 8: Настройка HTTPS доступа (5 минут)

```bash
# 8.1. Установка Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy -y

# 8.2. Настройка Caddyfile
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

# 8.3. Запуск Caddy
systemctl enable --now caddy

# 8.4. Проверка HTTPS доступа
curl -k https://bi.zakaz-dashboard.ru/healthz
```

---

## ПРОВЕРКА РАБОТОСПОСОБНОСТИ (5 МИНУТ)

### Финальная проверка системы

```bash
# 1. Проверка ClickHouse
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SELECT 'ClickHouse OK'"

# 2. Проверка таблиц
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SHOW TABLES FROM zakaz"

# 3. Проверка прав пользователей
docker exec ch-zakaz clickhouse-client --user=admin --password='ВАШ_ПАРОЛЬ' -q "SHOW GRANTS FOR datalens_reader"

# 4. Проверка таймеров
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'

# 5. Проверка HTTPS доступа
curl -k https://bi.zakaz-dashboard.ru/?query=SELECT%201

# 6. Проверка загрузки данных (через 15 минут)
docker exec ch-zakaz clickhouse-client \
  --user=datalens_reader \
  --password='ChangeMe123!' \
  -q "SELECT count() FROM zakaz.stg_qtickets_api_orders_raw"
```

---

## ПРЕИМУЩЕСТВА ЧИСТОГО РАЗВЕРТЫВАНИЯ

### Преимущества перед исправлением существующей установки

1. **Нет наследуемых проблем** - все компоненты устанавливаются с нуля
2. **Предсказуемое время** - 40 минут от начала до конца
3. **Гарантия совместимости** - все компоненты одной версии
4. **Чистые логи** - нет остаточных данных от предыдущих установок
5. **Простая отладка** - все проблемы известны и задокументированы

### Сравнение с исправлением существующей установки

| Параметр | Чистое развертывание | Исправление существующего |
|-----------|-------------------|------------------------|
| Время | 40 минут | 2-4 часа |
| Надежность | Высокая | Средняя |
| Сложность | Низкая | Высокая |
| Риски | Минимальные | Средние |
| Отладка | Простая | Сложная |

---

## ВОССТАНОВЛЕНИЕ ДАННЫХ (ЕСЛИ ЕСТЬ БЭКАП)

### Восстановление из резервной копии

```bash
# Если у вас есть бэкап данных с предыдущего сервера
# 1. Остановите все сервисы
systemctl stop qtickets_api.timer vk_ads.timer direct.timer
docker-compose down

# 2. Восстановите данные
docker exec -i ch-zakaz clickhouse-client \
  --user=admin \
  --password='ВАШ_ПАРОЛЬ' \
  < backup_file.sql

# 3. Перезапустите сервисы
docker-compose up -d
systemctl start qtickets_api.timer vk_ads.timer direct.timer
```

---

## ТРАБЛШУТИНГ ЧИСТОГО РАЗВЕРТЫВАНИЯ

### Возможные проблемы и решения

1. **Docker не устанавливается**:
   ```bash
   # Решение:
   apt remove docker docker-engine
   apt autoremove
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```

2. **Git не клонирует репозиторий**:
   ```bash
   # Решение:
   apt install -y git
   git config --global http.sslverify false
   git clone https://github.com/tanislara292-ux/Zakaz_Dashboard.git .
   ```

3. **ClickHouse не запускается**:
   ```bash
   # Решение:
   docker-compose down
   docker system prune -f
   docker-compose up -d
   ```

4. **Порты заблокированы файрволом**:
   ```bash
   # Решение:
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw allow 8123/tcp
   ufw reload
   ```

---

## ЗАВЕРШЕНИЕ РАЗВЕРТЫВАНИЯ

После выполнения всех шагов у вас будет:

1. ✅ **Полностью функциональная система** Zakaz Dashboard
2. ✅ **ClickHouse** с правильной схемой и правами
3. ✅ **QTickets API** с настроенным токеном
4. ✅ **HTTPS доступ** через Caddy
5. ✅ **Автоматическая загрузка данных** через systemd таймеры
6. ✅ **Готовность к подключению** DataLens

### Передача заказчику

1. **Предоставьте доступы**:
   - URL дашбордов: `https://bi.zakaz-dashboard.ru`
   - Учетные данные ClickHouse
   - Учетные данные для DataLens

2. **Проведите обучение**:
   - Работа с дашбордами
   - Проверка свежести данных
   - Основные операции

3. **Передайте документацию**:
   - Финальная инструкция (этот файл)
   - Чек-лист для регулярных проверок
   - Контакты поддержки

---

## КОНТАКТЫ ПОДДЕРЖКИ

- **Техническая поддержка**: [контакт разработчика]
- **Экстренные случаи**: [экстренный контакт]
- **Документация**: [ссылка на документацию]

---

**Версия инструкции**: 1.0.0  
**Дата создания**: 2025-10-30  
**Последнее обновление**: 2025-10-30

---

*Эта инструкция предоставляет самый надежный способ развертывания Zakaz Dashboard на чистом сервере заказчика. Рекомендуется использовать этот подход для минимизации рисков и гарантии успешного развертывания.*