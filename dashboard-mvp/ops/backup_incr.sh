#!/bin/bash
# Инкрементальный бэкап ClickHouse
# Использование: ./backup_incr.sh [s3|local]

set -euo pipefail

# Загрузка переменных окружения
source "$(dirname "$0")/../.env"

# Параметры по умолчанию
BACKUP_MODE=${1:-${BACKUP_MODE:-s3}}
BACKUP_NAME="chbk_$(date +%Y%m%d_%H%M%S)_incr"
BACKUP_START=$(date +%s)
LOG_FILE="/tmp/backup_incr_${BACKUP_NAME}.log"

# Функции логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    log "ERROR: $1"
    update_backup_status "fail" "$1"
    exit 1
}

# Функция обновления статуса бэкапа
update_backup_status() {
    local status=$1
    local error_msg=${2:-""}
    local duration=$((($(date +%s) - BACKUP_START) * 1000))
    
    clickhouse-client --host localhost --port 8123 --user backup_user --password "${CLICKHOUSE_BACKUP_USER_PASSWORD}" --query "
        INSERT INTO meta.backup_runs (backup_name, mode, target, status, bytes, duration_ms, details, error_msg) 
        VALUES ('${BACKUP_NAME}', 'incr', '${BACKUP_TARGET}', '${status}', ${BACKUP_BYTES:-0}, ${duration}, '${BACKUP_DETAILS:-""}', '${error_msg}')
    " 2>/dev/null || true
}

# Проверка доступности ClickHouse
log "Проверка доступности ClickHouse"
if ! clickhouse-client --host localhost --port 8123 --query "SELECT 1" >/dev/null 2>&1; then
    error_exit "ClickHouse недоступен"
fi

# Поиск последнего полного бэкапа
LAST_FULL_BACKUP=$(clickhouse-client --host localhost --port 8123 --user backup_user --password "${CLICKHOUSE_BACKUP_USER_PASSWORD}" --query "
    SELECT backup_name FROM meta.backup_runs 
    WHERE mode = 'full' AND status = 'ok' 
    ORDER BY ts DESC LIMIT 1
" 2>/dev/null || echo "")

if [[ -z "$LAST_FULL_BACKUP" ]]; then
    error_exit "Не найден успешный полный бэкап для создания инкрементального. Сначала выполните полный бэкап."
fi

log "Найден последний полный бэкап: ${LAST_FULL_BACKUP}"

# Определение цели бэкапа
if [[ "$BACKUP_MODE" == "s3" ]]; then
    if [[ -z "${S3_BUCKET:-}" || -z "${S3_ACCESS_KEY:-}" || -z "${S3_SECRET_KEY:-}" ]]; then
        error_exit "Не настроены переменные S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY"
    fi
    BACKUP_TARGET="s3://${S3_BUCKET}/clickhouse-backups"
    BACKUP_CMD="BACKUP DATABASE zakaz, DATABASE bi, DATABASE meta TO S3('${S3_BUCKET}', '${S3_ACCESS_KEY}', '${S3_SECRET_KEY}', 'prefix=clickhouse-backups/') AS '${BACKUP_NAME}' SETTINGS base_backup='${LAST_FULL_BACKUP}'"
elif [[ "$BACKUP_MODE" == "local" ]]; then
    BACKUP_DIR=${BACKUP_DIR:-"/opt/clickhouse/backups"}
    mkdir -p "$BACKUP_DIR"
    BACKUP_TARGET="${BACKUP_DIR}/${BACKUP_NAME}"
    BACKUP_CMD="BACKUP DATABASE zakaz, DATABASE bi, DATABASE meta TO Disk('backups', '${BACKUP_NAME}') SETTINGS base_backup='${LAST_FULL_BACKUP}'"
else
    error_exit "Неподдерживаемый режим бэкапа: $BACKUP_MODE. Используйте s3 или local"
fi

# Проверка свободного места (для локального режима)
if [[ "$BACKUP_MODE" == "local" ]]; then
    # Оценочный размер инкрементального бэкапа (10% от полного)
    ESTIMATED_SIZE=$(clickhouse-client --host localhost --port 8123 --query "
        SELECT round(sum(bytes) * 0.1) FROM system.parts WHERE database IN ('zakaz', 'bi', 'meta') AND active = 1 AND modification_time > now() - INTERVAL 1 DAY
    " 2>/dev/null || echo "0")
    
    AVAILABLE_SPACE=$(df "$BACKUP_DIR" | awk 'NR==2 {print $4 * 1024}')  # в байтах
    
    if [[ $ESTIMATED_SIZE -gt $AVAILABLE_SPACE ]]; then
        error_exit "Недостаточно места для бэкапа. Требуется: ${ESTIMATED_SIZE} байт, доступно: ${AVAILABLE_SPACE} байт"
    fi
    
    log "Оценочный размер инкрементального бэкапа: $(($ESTIMATED_SIZE / 1024 / 1024)) MB"
fi

# Регистрация начала бэкапа
log "Начало инкрементального бэкапа: ${BACKUP_NAME}"
log "Режим: ${BACKUP_MODE}, цель: ${BACKUP_TARGET}"
log "Базовый бэкап: ${LAST_FULL_BACKUP}"
update_backup_status "running"

# Выполнение бэкапа
log "Выполнение команды инкрементального бэкапа..."
BACKUP_OUTPUT=$(clickhouse-client --host localhost --port 8123 --user backup_user --password "${CLICKHOUSE_BACKUP_USER_PASSWORD}" --query "$BACKUP_CMD" 2>&1) || error_exit "Ошибка выполнения бэкапа: $BACKUP_OUTPUT"

# Получение размера бэкапа
if [[ "$BACKUP_MODE" == "s3" ]]; then
    # Для S3 размер получить сложно, используем оценку
    BACKUP_BYTES=$(clickhouse-client --host localhost --port 8123 --query "
        SELECT round(sum(bytes) * 0.1) FROM system.parts WHERE database IN ('zakaz', 'bi', 'meta') AND active = 1 AND modification_time > now() - INTERVAL 1 DAY
    " 2>/dev/null || echo "0")
else
    # Для локального режима проверяем размер файлов
    if [[ -d "${BACKUP_DIR}/${BACKUP_NAME}" ]]; then
        BACKUP_BYTES=$(du -sb "${BACKUP_DIR}/${BACKUP_NAME}" | cut -f1)
    else
        BACKUP_BYTES=0
    fi
fi

BACKUP_DETAILS="Режим: ${BACKUP_MODE}, базы: zakaz, bi, meta, базовый: ${LAST_FULL_BACKUP}"

# Обновление статуса успешного завершения
update_backup_status "ok"

# Очистка старых инкрементальных бэкапов
log "Очистка старых инкрементальных бэкапов..."
if [[ "$BACKUP_MODE" == "local" ]]; then
    # Удаляем инкрементальные бэкапы старше 7 дней
    find "$BACKUP_DIR" -name "chbk_*_incr" -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
    log "Очистка локальных инкрементальных бэкапов завершена"
elif [[ "$BACKUP_MODE" == "s3" ]]; then
    # Для S3 очистка требует отдельного скрипта с aws-cli
    log "Очистка S3 бэкапов требует отдельного запуска backup_prune.sh"
fi

# Завершение
BACKUP_DURATION=$((($(date +%s) - BACKUP_START)))
log "Инкрементальный бэкап успешно завершен за ${BACKUP_DURATION} секунд"
log "Размер бэкапа: $(($BACKUP_BYTES / 1024 / 1024)) MB"
log "Имя бэкапа: ${BACKUP_NAME}"

# Отправка алерта (если настроен)
if [[ -n "${TG_BOT_TOKEN:-}" && -n "${TG_CHAT_ID:-}" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TG_CHAT_ID}" \
        -d text="🔄 ClickHouse инкрементальный бэкап успешно выполнен: ${BACKUP_NAME} (${BACKUP_MODE}, $(($BACKUP_BYTES / 1024 / 1024)) MB)" \
        >/dev/null 2>&1 || true
fi

exit 0