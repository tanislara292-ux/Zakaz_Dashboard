#!/bin/bash
# Тестовое восстановление бэкапа ClickHouse в изолированном контейнере
# Использование: ./restore_test.sh [backup_name] [s3|local]

set -euo pipefail

# Загрузка переменных окружения
source "$(dirname "$0")/../.env"

# Параметры
BACKUP_NAME=${1:-""}
BACKUP_MODE=${2:-${BACKUP_MODE:-s3}}
TEST_START=$(date +%s)
LOG_FILE="/tmp/restore_test_${BACKUP_NAME:-$(date +%Y%m%d_%H%M%S)}.log"
TEST_CONTAINER="ch-restore-test-$$"
TEST_PORT=$((8123 + $$ % 1000))  # Уникальный порт для теста

# Функции логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    log "ERROR: $1"
    cleanup
    exit 1
}

cleanup() {
    log "Очистка тестового окружения..."
    
    # Остановка и удаление контейнера
    if docker ps -q -f name="$TEST_CONTAINER" | grep -q .; then
        docker stop "$TEST_CONTAINER" >/dev/null 2>&1 || true
    fi
    
    if docker ps -a -q -f name="$TEST_CONTAINER" | grep -q .; then
        docker rm "$TEST_CONTAINER" >/dev/null 2>&1 || true
    fi
    
    # Удаление временных файлов
    rm -f /tmp/ch-restore-test-$$.*
    
    log "Очистка завершена"
}

# Функция проверки данных после восстановления
verify_data() {
    log "Проверка восстановленных данных..."
    
    # Проверка наличия таблиц
    local tables=(
        "zakaz.stg_qtickets_sales"
        "zakaz.stg_vk_ads_daily"
        "zakaz.dm_sales_daily"
        "zakaz.dm_vk_ads_daily"
        "bi.v_sales_daily"
        "bi.v_vk_ads_daily"
        "meta.backup_runs"
    )
    
    for table in "${tables[@]}"; do
        local count=$(docker exec "$TEST_CONTAINER" clickhouse-client --query "SELECT count() FROM $table" 2>/dev/null || echo "0")
        log "Таблица $table: $count строк"
        
        # Проверяем, что в таблицах есть данные (кроме backup_runs)
        if [[ "$table" != "meta.backup_runs" && "$count" == "0" ]]; then
            log "WARNING: Таблица $table пуста"
        fi
    done
    
    # Проверка целостности данных
    local sales_count=$(docker exec "$TEST_CONTAINER" clickhouse-client --query "SELECT count() FROM zakaz.dm_sales_daily" 2>/dev/null || echo "0")
    local vk_count=$(docker exec "$TEST_CONTAINER" clickhouse-client --query "SELECT count() FROM zakaz.dm_vk_ads_daily" 2>/dev/null || echo "0")
    
    if [[ $sales_count -gt 0 ]]; then
        local sample_revenue=$(docker exec "$TEST_CONTAINER" clickhouse-client --query "SELECT sum(net_revenue) FROM zakaz.dm_sales_daily LIMIT 1" 2>/dev/null || echo "0")
        log "Пример выручки: $sample_revenue"
    fi
    
    if [[ $vk_count -gt 0 ]]; then
        local sample_spend=$(docker exec "$TEST_CONTAINER" clickhouse-client --query "SELECT sum(spend) FROM zakaz.dm_vk_ads_daily LIMIT 1" 2>/dev/null || echo "0")
        log "Пример расходов: $sample_spend"
    fi
    
    log "Проверка данных завершена"
}

# Обработка сигналов для корректной очистки
trap cleanup EXIT INT TERM

# Поиск бэкапа для восстановления
if [[ -z "$BACKUP_NAME" ]]; then
    log "Поиск последнего успешного бэкапа..."
    BACKUP_NAME=$(clickhouse-client --host localhost --port 8123 --user backup_user --password "${CLICKHOUSE_BACKUP_USER_PASSWORD}" --query "
        SELECT backup_name FROM meta.backup_runs 
        WHERE status = 'ok' 
        ORDER BY ts DESC LIMIT 1
    " 2>/dev/null || echo "")
    
    if [[ -z "$BACKUP_NAME" ]]; then
        error_exit "Не найден успешный бэкап для восстановления"
    fi
fi

log "Используется бэкап: ${BACKUP_NAME}"

# Проверка доступности основного ClickHouse
if ! clickhouse-client --host localhost --port 8123 --query "SELECT 1" >/dev/null 2>&1; then
    error_exit "Основной ClickHouse недоступен"
fi

# Создание временной директории для тестов
TEMP_DIR=$(mktemp -d -p /tmp ch-restore-test-$$-XXXXXX)
mkdir -p "$TEMP_DIR/data"

# Подготовка команды восстановления
if [[ "$BACKUP_MODE" == "s3" ]]; then
    if [[ -z "${S3_BUCKET:-}" || -z "${S3_ACCESS_KEY:-}" || -z "${S3_SECRET_KEY:-}" ]]; then
        error_exit "Не настроены переменные S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY"
    fi
    
    RESTORE_CMD="RESTORE DATABASE zakaz, DATABASE bi, DATABASE meta FROM S3('${S3_BUCKET}', '${S3_ACCESS_KEY}', '${S3_SECRET_KEY}', 'prefix=clickhouse-backups/') AS '${BACKUP_NAME}'"
elif [[ "$BACKUP_MODE" == "local" ]]; then
    BACKUP_DIR=${BACKUP_DIR:-"/opt/clickhouse/backups"}
    
    if [[ ! -d "${BACKUP_DIR}/${BACKUP_NAME}" ]]; then
        error_exit "Бэкап не найден: ${BACKUP_DIR}/${BACKUP_NAME}"
    fi
    
    # Копируем бэкап во временную директорию для монтирования в контейнер
    cp -r "${BACKUP_DIR}/${BACKUP_NAME}" "$TEMP_DIR/"
    
    RESTORE_CMD="RESTORE DATABASE zakaz, DATABASE bi, DATABASE meta FROM Disk('backups', '${BACKUP_NAME}')"
else
    error_exit "Неподдерживаемый режим бэкапа: $BACKUP_MODE. Используйте s3 или local"
fi

# Создание временного конфига для тестового контейнера
cat > "$TEMP_DIR/config.xml" <<EOF
<clickhouse>
    <logger>
        <level>warning</level>
        <console>true</console>
    </logger>
    
    <http_port>8123</http_port>
    <tcp_port>9000</tcp_port>
    
    <listen_host>0.0.0.0</listen_host>
    
    <path>/var/lib/clickhouse/</path>
    <tmp_path>/var/lib/clickhouse/tmp/</tmp_path>
    <user_files_path>/var/lib/clickhouse/user_files/</user_files_path>
    
    <users_config>users.xml</users_config>
    <default_profile>default</default_profile>
    <default_database>default</default_database>
    
    <timezone>Europe/Moscow</timezone>
    
    <display_name>test</display_name>
    
    <mark_cache_size>5368709120</mark_cache_size>
    
    <path_to_regions_config>/etc/clickhouse-server/regions_config.xml</path_to_regions_config>
</clickhouse>
EOF

# Создание конфига пользователей для тестового контейнера
cat > "$TEMP_DIR/users.xml" <<EOF
<clickhouse>
    <users>
        <default>
            <password/>
            <networks>
                <ip>::/0</ip>
            </networks>
            <profile>default</profile>
            <quota>default</quota>
        </default>
    </users>
</clickhouse>
EOF

# Запуск тестового контейнера ClickHouse
log "Запуск тестового контейнера ClickHouse..."
docker run -d \
    --name "$TEST_CONTAINER" \
    -p "$TEST_PORT:8123" \
    -v "$TEMP_DIR/config.xml:/etc/clickhouse-server/config.xml" \
    -v "$TEMP_DIR/users.xml:/etc/clickhouse-server/users.xml" \
    -v "$TEMP_DIR/data:/var/lib/clickhouse" \
    -v "$TEMP_DIR:/backups" \
    --tmpfs /tmp \
    clickhouse/clickhouse-server:24.8

# Ожидание запуска ClickHouse
log "Ожидание запуска ClickHouse..."
for i in {1..60}; do
    if docker exec "$TEST_CONTAINER" clickhouse-client --query "SELECT 1" >/dev/null 2>&1; then
        log "ClickHouse запущен за $i попыток"
        break
    fi
    
    if [[ $i -eq 60 ]]; then
        error_exit "ClickHouse не запустился за 60 секунд"
    fi
    
    sleep 1
done

# Инициализация структуры баз данных (если нужно)
log "Инициализация структуры баз данных..."
docker exec "$TEST_CONTAINER" clickhouse-client --query "
    CREATE DATABASE IF NOT EXISTS zakaz;
    CREATE DATABASE IF NOT EXISTS bi;
    CREATE DATABASE IF NOT EXISTS meta;
" || error_exit "Ошибка создания баз данных"

# Выполнение восстановления
log "Выполнение восстановления из бэкапа..."
RESTORE_OUTPUT=$(docker exec "$TEST_CONTAINER" clickhouse-client --query "$RESTORE_CMD" 2>&1) || error_exit "Ошибка восстановления: $RESTORE_OUTPUT"

log "Восстановление успешно завершено"

# Проверка восстановленных данных
verify_data

# Расчет времени выполнения
RESTORE_DURATION=$((($(date +%s) - TEST_START)))
log "Тестовое восстановление успешно завершено за ${RESTORE_DURATION} секунд"

# Отправка алерта (если настроен)
if [[ -n "${TG_BOT_TOKEN:-}" && -n "${TG_CHAT_ID:-}" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TG_CHAT_ID}" \
        -d text="✅ Тестовое восстановление ClickHouse успешно выполнено: ${BACKUP_NAME} (${BACKUP_MODE}, ${RESTORE_DURATION} сек)" \
        >/dev/null 2>&1 || true
fi

# Очистка будет выполнена автоматически через trap
log "Тестовое восстановление завершено успешно"

exit 0