#!/bin/bash
# Очистка старых бэкапов ClickHouse
# Использование: ./backup_prune.sh [s3|local]

set -euo pipefail

# Загрузка переменных окружения
source "$(dirname "$0")/../.env"

# Параметры по умолчанию
BACKUP_MODE=${1:-${BACKUP_MODE:-s3}}
LOG_FILE="/tmp/backup_prune_$(date +%Y%m%d_%H%M%S).log"

# Политика хранения (в днях)
FULL_RETENTION_DAYS=${FULL_RETENTION_DAYS:-28}      # Полные бэкапы: 4 недели
INCR_RETENTION_DAYS=${INCR_RETENTION_DAYS:-7}      # Инкрементальные: 7 дней
GOLDEN_RETENTION_MONTHS=${GOLDEN_RETENTION_MONTHS:-12}  # Золотые бэкапы: 1 год (квартальные)

# Функции логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

# Проверка доступности ClickHouse
log "Проверка доступности ClickHouse"
if ! clickhouse-client --host localhost --port 8123 --query "SELECT 1" >/dev/null 2>&1; then
    error_exit "ClickHouse недоступен"
fi

# Функция для проверки, является ли бэкап золотым (квартальным)
is_golden_backup() {
    local backup_name=$1
    local backup_date=$(echo "$backup_name" | sed -n 's/.*_\([0-9]\{8\)_\).*/\1/p')
    
    if [[ -z "$backup_date" ]]; then
        return 1  # Не удалось извлечь дату
    fi
    
    local year=${backup_date:0:4}
    local month=${backup_date:4:2}
    
    # Проверяем, первый ли день квартала (1 января, 1 апреля, 1 июля, 1 октября)
    if [[ "$month" == "01" || "$month" == "04" || "$month" == "07" || "$month" == "10" ]]; then
        # Для простоты считаем все бэкапы первого дня месяца как потенциально золотые
        return 0
    fi
    
    return 1
}

# Получение списка бэкапов для удаления
log "Получение списка бэкапов для удаления..."

# Полные бэкапы старше FULL_RETENTION_DAYS
FULL_TO_DELETE=$(clickhouse-client --host localhost --port 8123 --user backup_user --password "${CLICKHOUSE_BACKUP_USER_PASSWORD}" --format TabSeparated --query "
    SELECT backup_name 
    FROM meta.backup_runs 
    WHERE mode = 'full' 
      AND status = 'ok' 
      AND ts < now() - INTERVAL ${FULL_RETENTION_DAYS} DAY
    ORDER BY ts ASC
" 2>/dev/null || true)

# Инкрементальные бэкапы старше INCR_RETENTION_DAYS
INCR_TO_DELETE=$(clickhouse-client --host localhost --port 8123 --user backup_user --password "${CLICKHOUSE_BACKUP_USER_PASSWORD}" --format TabSeparated --query "
    SELECT backup_name 
    FROM meta.backup_runs 
    WHERE mode = 'incr' 
      AND status = 'ok' 
      AND ts < now() - INTERVAL ${INCR_RETENTION_DAYS} DAY
    ORDER BY ts ASC
" 2>/dev/null || true)

# Объединяем списки
ALL_TO_DELETE=""
for backup in $FULL_TO_DELETE; do
    if ! is_golden_backup "$backup"; then
        ALL_TO_DELETE="${ALL_TO_DELETE}${backup}\n"
    else
        log "Пропуск золотого бэкапа: $backup"
    fi
done

for backup in $INCR_TO_DELETE; do
    ALL_TO_DELETE="${ALL_TO_DELETE}${backup}\n"
done

if [[ -z "$ALL_TO_DELETE" ]]; then
    log "Нет бэкапов для удаления"
    exit 0
fi

log "Найдено $(echo -e "$ALL_TO_DELETE" | grep -c '^') бэкапов для удаления"

# Удаление бэкапов
DELETED_COUNT=0
DELETED_SIZE=0

while IFS= read -r backup_name; do
    if [[ -z "$backup_name" ]]; then
        continue
    fi
    
    log "Удаление бэкапа: $backup_name"
    
    if [[ "$BACKUP_MODE" == "local" ]]; then
        BACKUP_DIR=${BACKUP_DIR:-"/opt/clickhouse/backups"}
        BACKUP_PATH="${BACKUP_DIR}/${backup_name}"
        
        if [[ -d "$BACKUP_PATH" ]]; then
            # Получаем размер перед удалением
            SIZE_BYTES=$(du -sb "$BACKUP_PATH" 2>/dev/null | cut -f1 || echo "0")
            DELETED_SIZE=$((DELETED_SIZE + SIZE_BYTES))
            
            # Удаляем бэкап
            rm -rf "$BACKUP_PATH" && DELETED_COUNT=$((DELETED_COUNT + 1))
            log "Удален локальный бэкап: $backup_name ($(($SIZE_BYTES / 1024 / 1024)) MB)"
        else
            log "Бэкап не найден: $BACKUP_PATH"
        fi
    elif [[ "$BACKUP_MODE" == "s3" ]]; then
        if ! command -v aws &> /dev/null; then
            error_exit "AWS CLI не установлен для работы с S3"
        fi
        
        if [[ -z "${S3_BUCKET:-}" ]]; then
            error_exit "Не настроена переменная S3_BUCKET"
        fi
        
        # Удаляем бэкап из S3
        if aws s3 rm "s3://${S3_BUCKET}/clickhouse-backups/${backup_name}" --recursive 2>/dev/null; then
            DELETED_COUNT=$((DELETED_COUNT + 1))
            log "Удален S3 бэкап: $backup_name"
        else
            log "Ошибка удаления S3 бэкапа: $backup_name"
        fi
    fi
    
    # Обновляем запись в meta.backup_runs
    clickhouse-client --host localhost --port 8123 --user backup_user --password "${CLICKHOUSE_BACKUP_USER_PASSWORD}" --query "
        ALTER TABLE meta.backup_runs UPDATE status = 'deleted', details = 'Deleted on $(date)' 
        WHERE backup_name = '${backup_name}'
    " 2>/dev/null || true
    
done <<< "$ALL_TO_DELETE"

log "Очистка завершена. Удалено $DELETED_COUNT бэкапов, освобождено $(($DELETED_SIZE / 1024 / 1024)) MB"

# Проверка оставшихся бэкапов
REMAINING_COUNT=$(clickhouse-client --host localhost --port 8123 --query "
    SELECT count() FROM meta.backup_runs WHERE status = 'ok'
" 2>/dev/null || echo "0")

log "Осталось активных бэкапов: $REMAINING_COUNT"

# Отправка алерта (если настроен)
if [[ -n "${TG_BOT_TOKEN:-}" && -n "${TG_CHAT_ID:-}" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TG_CHAT_ID}" \
        -d text="🧹 Очистка бэкапов ClickHouse завершена: удалено ${DELETED_COUNT} бэкапов, освобождено $(($DELETED_SIZE / 1024 / 1024)) MB" \
        >/dev/null 2>&1 || true
fi

exit 0