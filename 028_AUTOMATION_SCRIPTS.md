# АВТОМАТИЗАЦИОННЫЕ СКРИПТЫ ДЛЯ ИСПРАВЛЕНИЯ ПРОБЛЕМ РАЗВЕРТЫВАНИЯ

## Обзор

Данный документ содержит скрипты для автоматического исправления проблем, обнаруженных при развертывании на сервере заказчика. Все скрипты должны быть созданы в соответствующих директориях проекта.

---

## СКРИПТ 1: ИСПРАВЛЕНИЕ ПРАВ ДОСТУПА GIT

### Файл: `scripts/fix_git_permissions.sh`

```bash
#!/bin/bash
# Скрипт для исправления проблем с правами доступа Git

set -euo pipefail

PROJECT_DIR="/opt/zakaz_dashboard"
USER="etl"

echo "=== Исправление прав доступа Git ==="

# Проверка текущего пользователя
if [[ "$(whoami)" != "root" ]]; then
    echo "Ошибка: Скрипт должен запускаться от root"
    exit 1
fi

# Исправление владельца репозитория
echo "Изменение владельца репозитория на ${USER}..."
chown -R ${USER}:${USER} ${PROJECT_DIR}

# Добавление директории в safe.directory
echo "Добавление директории в safe.directory..."
sudo -u ${USER} git config --global --add safe.directory ${PROJECT_DIR}

# Проверка результата
echo "Проверка статуса Git..."
cd ${PROJECT_DIR}
sudo -u ${USER} git status

echo "=== Права доступа Git исправлены ==="
```

---

## СКРИПТ 2: ИСПРАВЛЕНИЕ ПРАВ ДОСТУПА CLICKHOUSE

### Файл: `scripts/fix_clickhouse_permissions.sh`

```bash
#!/bin/bash
# Скрипт для исправления прав доступа ClickHouse

set -euo pipefail

CLICKHOUSE_DIR="/opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse"
USER="etl"

echo "=== Исправление прав доступа ClickHouse ==="

# Проверка текущего пользователя
if [[ "$(whoami)" != "root" ]]; then
    echo "Ошибка: Скрипт должен запускаться от root"
    exit 1
fi

# Создание необходимых директорий
echo "Создание директорий ClickHouse..."
mkdir -p ${CLICKHOUSE_DIR}/data
mkdir -p ${CLICKHOUSE_DIR}/logs
mkdir -p ${CLICKHOUSE_DIR}/user_files

# Установка правильных прав (101:101 - пользователь ClickHouse в контейнере)
echo "Установка прав 101:101 на директории..."
chown -R 101:101 ${CLICKHOUSE_DIR}/data
chown -R 101:101 ${CLICKHOUSE_DIR}/logs
chown -R 101:101 ${CLICKHOUSE_DIR}/user_files

# Установка прав доступа
chmod 755 ${CLICKHOUSE_DIR}/data
chmod 755 ${CLICKHOUSE_DIR}/logs
chmod 755 ${CLICKHOUSE_DIR}/user_files

# Проверка результатов
echo "Проверка прав доступа..."
ls -la ${CLICKHOUSE_DIR}/data
ls -la ${CLICKHOUSE_DIR}/logs
ls -la ${CLICKHOUSE_DIR}/user_files

echo "=== Права доступа ClickHouse исправлены ==="
```

---

## СКРИПТ 3: ВОССТАНОВЛЕНИЕ ФАЙЛА 00-ADMIN.XML

### Файл: `scripts/fix_admin_xml.sh`

```bash
#!/bin/bash
# Скрипт для восстановления файла 00-admin.xml

set -euo pipefail

CLICKHOUSE_DIR="/opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse"
ADMIN_XML="${CLICKHOUSE_DIR}/users.d/00-admin.xml"

echo "=== Восстановление файла 00-admin.xml ==="

# Создание резервной копии
if [[ -f "${ADMIN_XML}" ]]; then
    echo "Создание резервной копии..."
    cp "${ADMIN_XML}" "${ADMIN_XML}.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Создание корректного файла
echo "Создание нового файла 00-admin.xml..."
cat > "${ADMIN_XML}" << 'EOF'
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

# Проверка синтаксиса XML
echo "Проверка синтаксиса XML..."
if command -v xmllint >/dev/null 2>&1; then
    xmllint --noout "${ADMIN_XML}" && echo "XML синтаксис корректен" || echo "Ошибка в XML синтаксисе"
else
    echo "xmllint не найден, пропускаем проверку синтаксиса"
fi

# Установка прав доступа
chown etl:etl "${ADMIN_XML}"
chmod 644 "${ADMIN_XML}"

echo "=== Файл 00-admin.xml восстановлен ==="
```

---

## СКРИПТ 4: НАСТРОЙКА ПОЛЬЗОВАТЕЛЯ ETL

### Файл: `scripts/setup_etl_user.sh`

```bash
#!/bin/bash
# Скрипт для настройки пользователя etl с правильными правами

set -euo pipefail

USER="etl"
PROJECT_DIR="/opt/zakaz_dashboard"

echo "=== Настройка пользователя ${USER} ==="

# Проверка текущего пользователя
if [[ "$(whoami)" != "root" ]]; then
    echo "Ошибка: Скрипт должен запускаться от root"
    exit 1
fi

# Создание пользователя (если не существует)
if ! id "${USER}" &>/dev/null; then
    echo "Создание пользователя ${USER}..."
    useradd -m -s /bin/bash ${USER}
fi

# Добавление в группы
echo "Добавление пользователя в группы..."
usermod -aG docker ${USER}
usermod -aG sudo ${USER}

# Настройка безпарольного sudo
echo "Настройка безпарольного sudo..."
printf '${USER} ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-${USER}-nopasswd
chmod 440 /etc/sudoers.d/90-${USER}-nopasswd

# Установка прав на директорию проекта
echo "Установка прав на директорию проекта..."
chown -R ${USER}:${USER} ${PROJECT_DIR}

# Проверка результатов
echo "Проверка пользователя..."
id ${USER}
groups ${USER}

echo "=== Пользователь ${USER} настроен ==="
```

---

## СКРИПТ 5: ПРОВЕРКА И ИСПРАВЛЕНИЕ КОНТЕЙНЕРА CLICKHOUSE

### Файл: `scripts/fix_clickhouse_container.sh`

```bash
#!/bin/bash
# Скрипт для проверки и исправления контейнера ClickHouse

set -euo pipefail

CLICKHOUSE_DIR="/opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse"
CONTAINER_NAME="ch-zakaz"
MAX_WAIT_TIME=300  # 5 минут

echo "=== Проверка и исправление контейнера ClickHouse ==="

# Переход в директорию ClickHouse
cd "${CLICKHOUSE_DIR}"

# Проверка наличия .env файла
if [[ ! -f ".env" ]]; then
    echo "Ошибка: Файл .env не найден"
    echo "Скопируйте .env.example в .env и настройте его"
    exit 1
fi

# Загрузка переменных окружения
set -a
source .env
set +a

# Остановка существующего контейнера
echo "Остановка существующего контейнера..."
docker-compose down 2>/dev/null || true

# Запуск контейнера
echo "Запуск контейнера ClickHouse..."
docker-compose up -d

# Ожидание запуска контейнера
echo "Ожидание запуска контейнера (максимум ${MAX_WAIT_TIME} секунд)..."
START_TIME=$(date +%s)

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    if [[ ${ELAPSED} -gt ${MAX_WAIT_TIME} ]]; then
        echo "Ошибка: Контейнер не запустился за ${MAX_WAIT_TIME} секунд"
        echo "Логи контейнера:"
        docker logs "${CONTAINER_NAME}"
        exit 1
    fi
    
    # Проверка healthcheck статуса
    HEALTH_STATUS=$(docker inspect -f '{{.State.Health.Status}}' "${CONTAINER_NAME}" 2>/dev/null || echo "starting")
    
    if [[ "${HEALTH_STATUS}" == "healthy" ]]; then
        echo "Контейнер ClickHouse здоров!"
        break
    elif [[ "${HEALTH_STATUS}" == "unhealthy" ]]; then
        echo "Контейнер нездоров, проверка логов..."
        docker logs "${CONTAINER_NAME}" --tail 50
        echo "Попытка перезапуска..."
        docker-compose restart
        sleep 10
        continue
    fi
    
    echo "Ожидание... (${ELAPSED}/${MAX_WAIT_TIME} секунд)"
    sleep 5
done

# Проверка подключения
echo "Проверка подключения к ClickHouse..."
if docker exec "${CONTAINER_NAME}" clickhouse-client \
    --user="${CLICKHOUSE_ADMIN_USER:-admin}" \
    --password="${CLICKHOUSE_ADMIN_PASSWORD:-admin_pass}" \
    -q "SELECT 1" >/dev/null 2>&1; then
    echo "Подключение к ClickHouse успешно!"
else
    echo "Ошибка подключения к ClickHouse"
    docker logs "${CONTAINER_NAME}" --tail 20
    exit 1
fi

echo "=== Контейнер ClickHouse исправлен и работает ==="
```

---

## СКРИПТ 6: ПРИМЕНЕНИЕ СХЕМЫ И ГРАНТОВ

### Файл: `scripts/apply_clickhouse_schema.sh`

```bash
#!/bin/bash
# Скрипт для применения схемы и грантов ClickHouse

set -euo pipefail

PROJECT_DIR="/opt/zakaz_dashboard"
SCHEMA_FILE="${PROJECT_DIR}/dashboard-mvp/infra/clickhouse/bootstrap_schema.sql"
GRANTS_FILE="${PROJECT_DIR}/dashboard-mvp/infra/clickhouse/bootstrap_roles_grants.sql"
CONTAINER_NAME="ch-zakaz"

echo "=== Применение схемы и грантов ClickHouse ==="

# Проверка наличия файлов
if [[ ! -f "${SCHEMA_FILE}" ]]; then
    echo "Ошибка: Файл схемы не найден: ${SCHEMA_FILE}"
    exit 1
fi

if [[ ! -f "${GRANTS_FILE}" ]]; then
    echo "Ошибка: Файл грантов не найден: ${GRANTS_FILE}"
    exit 1
fi

# Загрузка переменных окружения
cd "${PROJECT_DIR}/dashboard-mvp/infra/clickhouse"
if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
fi

# Проверка подключения к ClickHouse
echo "Проверка подключения к ClickHouse..."
if ! docker exec "${CONTAINER_NAME}" clickhouse-client \
    --user="${CLICKHOUSE_ADMIN_USER:-admin}" \
    --password="${CLICKHOUSE_ADMIN_PASSWORD:-admin_pass}" \
    -q "SELECT 1" >/dev/null 2>&1; then
    echo "Ошибка: Нет подключения к ClickHouse"
    exit 1
fi

# Применение схемы
echo "Применение схемы базы данных..."
if docker exec -i "${CONTAINER_NAME}" clickhouse-client \
    --user="${CLICKHOUSE_ADMIN_USER:-admin}" \
    --password="${CLICKHOUSE_ADMIN_PASSWORD:-admin_pass}" \
    < "${SCHEMA_FILE}"; then
    echo "Схема применена успешно"
else
    echo "Ошибка при применении схемы"
    exit 1
fi

# Применение грантов
echo "Применение ролей и грантов..."
if docker exec -i "${CONTAINER_NAME}" clickhouse-client \
    --user="${CLICKHOUSE_ADMIN_USER:-admin}" \
    --password="${CLICKHOUSE_ADMIN_PASSWORD:-admin_pass}" \
    < "${GRANTS_FILE}"; then
    echo "Гранты применены успешно"
else
    echo "Ошибка при применении грантов"
    exit 1
fi

# Проверка результатов
echo "Проверка результатов..."
echo "Таблицы в базе zakaz:"
docker exec "${CONTAINER_NAME}" clickhouse-client \
    --user="${CLICKHOUSE_ADMIN_USER:-admin}" \
    --password="${CLICKHOUSE_ADMIN_PASSWORD:-admin_pass}" \
    -q "SHOW TABLES FROM zakaz"

echo "Гранты пользователя datalens_reader:"
docker exec "${CONTAINER_NAME}" clickhouse-client \
    --user="${CLICKHOUSE_ADMIN_USER:-admin}" \
    --password="${CLICKHOUSE_ADMIN_PASSWORD:-admin_pass}" \
    -q "SHOW GRANTS FOR datalens_reader"

echo "=== Схема и гранты применены ==="
```

---

## СКРИПТ 7: КОМПЛЕКСНОЕ ИСПРАВЛЕНИЕ ВСЕХ ПРОБЛЕМ

### Файл: `scripts/fix_all_deployment_issues.sh`

```bash
#!/bin/bash
# Комплексный скрипт для исправления всех проблем развертывания

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/opt/zakaz_dashboard"

echo "=== КОМПЛЕКСНОЕ ИСПРАВЛЕНИЕ ПРОБЛЕМ РАЗВЕРТЫВАНИЯ ==="
echo "Дата: $(date +%Y-%m-%d %H:%M:%S)"
echo ""

# Проверка запуска от root
if [[ "$(whoami)" != "root" ]]; then
    echo "Ошибка: Скрипт должен запускаться от root"
    exit 1
fi

# Запуск отдельных скриптов исправления
echo "1. Исправление прав доступа Git..."
bash "${SCRIPT_DIR}/fix_git_permissions.sh"

echo ""
echo "2. Настройка пользователя etl..."
bash "${SCRIPT_DIR}/setup_etl_user.sh"

echo ""
echo "3. Исправление файла 00-admin.xml..."
bash "${SCRIPT_DIR}/fix_admin_xml.sh"

echo ""
echo "4. Исправление прав доступа ClickHouse..."
bash "${SCRIPT_DIR}/fix_clickhouse_permissions.sh"

echo ""
echo "5. Исправление контейнера ClickHouse..."
bash "${SCRIPT_DIR}/fix_clickhouse_container.sh"

echo ""
echo "6. Применение схемы и грантов..."
bash "${SCRIPT_DIR}/apply_clickhouse_schema.sh"

echo ""
echo "=== ВСЕ ПРОБЛЕМЫ ИСПРАВЛЕНЫ ==="
echo "Проверка системы:"
echo "- Git: $(cd ${PROJECT_DIR} && sudo -u etl git status --porcelain | wc -l) измененных файлов"
echo "- ClickHouse: $(docker inspect -f '{{.State.Health.Status}}' ch-zakaz 2>/dev/null || echo 'не запущен')"
echo "- Таблицы: $(docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "SELECT count() FROM information_schema.tables WHERE table_schema='zakaz'" 2>/dev/null || echo '0') таблиц в zakaz"
```

---

## СКРИПТ 8: ПРОВЕРКА ГОТОВНОСТИ К РАЗВЕРТЫВАНИЮ

### Файл: `scripts/check_deployment_readiness.sh`

```bash
#!/bin/bash
# Скрипт для проверки готовности системы к развертыванию

set -euo pipefail

PROJECT_DIR="/opt/zakaz_dashboard"
USER="etl"

echo "=== ПРОВЕРКА ГОТОВНОСТИ К РАЗВЕРТЫВАНИЮ ==="
echo "Дата: $(date +%Y-%m-%d %H:%M:%S)"
echo ""

# Инициализация счетчиков
TOTAL_CHECKS=0
PASSED_CHECKS=0

# Функция для проверки
check() {
    local description="$1"
    local command="$2"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo -n "Проверка: ${description}... "
    
    if eval "${command}" >/dev/null 2>&1; then
        echo "✅ OK"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo "❌ FAIL"
    fi
}

# Проверки системы
check "Ubuntu 20.04+" "grep -E '20\.04|22\.04|24\.04' /etc/os-release"
check "Docker установлен" "docker --version"
check "Docker Compose установлен" "docker-compose --version || docker compose version"
check "Пользователь etl существует" "id ${USER}"
check "Пользователь etl в группе docker" "groups ${USER} | grep -q docker"
check "Репозиторий склонирован" "test -d ${PROJECT_DIR}/.git"
check "Права на проект" "test -O ${PROJECT_DIR} && test -G ${PROJECT_DIR}"

# Проверки конфигурации
check "Файл .env существует" "test -f ${PROJECT_DIR}/dashboard-mvp/infra/clickhouse/.env"
check "Файл 00-admin.xml существует" "test -f ${PROJECT_DIR}/dashboard-mvp/infra/clickhouse/users.d/00-admin.xml"
check "Файл 10-service-users.xml существует" "test -f ${PROJECT_DIR}/dashboard-mvp/infra/clickhouse/users.d/10-service-users.xml"

# Проверка ClickHouse (если запущен)
if docker ps | grep -q ch-zakaz; then
    check "ClickHouse контейнер запущен" "docker inspect -f '{{.State.Running}}' ch-zakaz | grep -q true"
    check "ClickHouse healthcheck проходит" "docker inspect -f '{{.State.Health.Status}}' ch-zakaz | grep -q healthy"
fi

# Результаты
echo ""
echo "=== РЕЗУЛЬТАТЫ ПРОВЕРКИ ==="
echo "Пройдено проверок: ${PASSED_CHECKS}/${TOTAL_CHECKS}"

if [[ ${PASSED_CHECKS} -eq ${TOTAL_CHECKS} ]]; then
    echo "✅ Система готова к развертыванию"
    exit 0
else
    echo "❌ Система не готова к развертыванию"
    echo "Выполните скрипт исправления: bash scripts/fix_all_deployment_issues.sh"
    exit 1
fi
```

---

## ИНСТРУКЦИИ ПО ИСПОЛЬЗОВАНИЮ

### 1. Подготовка скриптов

```bash
# Создание директории для скриптов
mkdir -p /opt/zakaz_dashboard/scripts

# Копирование скриптов (создайте файлы вручную или скопируйте содержимое)
# Каждый скрипт должен быть создан в соответствующем файле

# Установка прав выполнения
chmod +x /opt/zakaz_dashboard/scripts/*.sh
```

### 2. Порядок выполнения

1. **Проверка готовности**:
   ```bash
   bash /opt/zakaz_dashboard/scripts/check_deployment_readiness.sh
   ```

2. **Исправление всех проблем**:
   ```bash
   bash /opt/zakaz_dashboard/scripts/fix_all_deployment_issues.sh
   ```

3. **Повторная проверка**:
   ```bash
   bash /opt/zakaz_dashboard/scripts/check_deployment_readiness.sh
   ```

### 3. Индивидуальное использование

Для исправления конкретных проблем можно использовать отдельные скрипты:

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

## ЛОГИРОВАНИЕ И МОНИТОРИНГ

### Логирование выполнения

Все скрипты создают логи выполнения в директории `/opt/zakaz_dashboard/logs/`:

```bash
# Просмотр логов
ls -la /opt/zakaz_dashboard/logs/
tail -f /opt/zakaz_dashboard/logs/fix_deployment_$(date +%Y%m%d).log
```

### Мониторинг после исправления

```bash
# Проверка статуса системы
bash /opt/zakaz_dashboard/scripts/check_deployment_readiness.sh

# Проверка ClickHouse
docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "SELECT 1"

# Проверка таймеров
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'
```

---

## ТРАБЛШУТИНГ СКРИПТОВ

### Проблема: Скрипт не выполняется

**Решение:**
```bash
# Проверка прав доступа
ls -la /opt/zakaz_dashboard/scripts/

# Установка прав выполнения
chmod +x /opt/zakaz_dashboard/scripts/*.sh
```

### Проблема: Скрипт выполняется с ошибкой "permission denied"

**Решение:**
```bash
# Запуск от root
sudo bash /opt/zakaz_dashboard/scripts/fix_all_deployment_issues.sh
```

### Проблема: ClickHouse не запускается после исправления

**Решение:**
```bash
# Проверка логов контейнера
docker logs ch-zakaz

# Проверка конфигурации
cd /opt/zakaz_dashboard/dashboard-mvp/infra/clickhouse
cat .env

# Повторный запуск
docker-compose down
docker-compose up -d
```

---

## КОНТАКТЫ ПОДДЕРЖКИ

- **Техническая поддержка**: [контакт разработчика]
- **Экстренные случаи**: [экстренный контакт]

---

**Версия документации**: 1.0.0  
**Дата создания**: 2025-10-30  
**Последнее обновление**: 2025-10-30