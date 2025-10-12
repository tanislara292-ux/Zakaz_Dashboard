#!/bin/bash

# Скрипт для управления systemd таймерами интеграций
# Использование: ./manage_timers.sh [start|stop|restart|status|enable|disable] [timer_name]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMERS_DIR="$SCRIPT_DIR"

# Список доступных таймеров
declare -A TIMERS=(
    ["qtickets"]="qtickets.timer"
    ["vk_ads"]="vk_ads.timer"
    ["direct"]="direct.timer"
    ["gmail"]="gmail_ingest.timer"
    ["alerts"]="alerts.timer"
)

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функции для вывода
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка root прав
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Этот скрипт должен быть запущен с правами root"
        exit 1
    fi
}

# Проверка существования таймера
check_timer() {
    local timer_name=$1
    local timer_file=${TIMERS[$timer_name]}
    
    if [[ -z "$timer_file" ]]; then
        print_error "Неизвестный таймер: $timer_name"
        print_info "Доступные таймеры: ${!TIMERS[*]}"
        exit 1
    fi
    
    if [[ ! -f "$TIMERS_DIR/$timer_file" ]]; then
        print_error "Файл таймера не найден: $TIMERS_DIR/$timer_file"
        exit 1
    fi
}

# Копирование файлов таймеров в systemd
install_timers() {
    print_info "Копирование файлов таймеров в systemd..."
    
    for timer_file in "${TIMERS[@]}"; do
        if [[ -f "$TIMERS_DIR/$timer_file" ]]; then
            cp "$TIMERS_DIR/$timer_file" "/etc/systemd/system/"
            print_info "Скопирован: $timer_file"
        fi
    done
    
    systemctl daemon-reload
    print_info "systemd daemon перезагружен"
}

# Показать статус всех таймеров
show_status() {
    print_info "Статус всех таймеров:"
    echo
    
    for timer_name in "${!TIMERS[@]}"; do
        local timer_file=${TIMERS[$timer_name]}
        echo "=== $timer_name ($timer_file) ==="
        
        if systemctl list-timers --all | grep -q "$timer_file"; then
            systemctl status "$timer_file" --no-pager -l
        else
            echo "Таймер не установлен"
        fi
        echo
    done
}

# Показать статус конкретного таймера
show_timer_status() {
    local timer_name=$1
    check_timer "$timer_name"
    local timer_file=${TIMERS[$timer_name]}
    
    print_info "Статус таймера $timer_name ($timer_file):"
    
    if systemctl list-timers --all | grep -q "$timer_file"; then
        systemctl status "$timer_file" --no-pager -l
    else
        print_warn "Таймер не установлен"
    fi
}

# Включить таймер
enable_timer() {
    local timer_name=$1
    check_timer "$timer_name"
    local timer_file=${TIMERS[$timer_name]}
    
    print_info "Включение таймера $timer_name..."
    
    systemctl enable "$timer_file"
    systemctl start "$timer_file"
    
    print_info "Таймер $timer_name включен и запущен"
}

# Отключить таймер
disable_timer() {
    local timer_name=$1
    check_timer "$timer_name"
    local timer_file=${TIMERS[$timer_name]}
    
    print_info "Отключение таймера $timer_name..."
    
    systemctl stop "$timer_file" 2>/dev/null || true
    systemctl disable "$timer_file"
    
    print_info "Таймер $timer_name отключен"
}

# Запустить таймер
start_timer() {
    local timer_name=$1
    check_timer "$timer_name"
    local timer_file=${TIMERS[$timer_name]}
    
    print_info "Запуск таймера $timer_name..."
    
    systemctl start "$timer_file"
    
    print_info "Таймер $timer_name запущен"
}

# Остановить таймер
stop_timer() {
    local timer_name=$1
    check_timer "$timer_name"
    local timer_file=${TIMERS[$timer_name]}
    
    print_info "Остановка таймера $timer_name..."
    
    systemctl stop "$timer_file"
    
    print_info "Таймер $timer_name остановлен"
}

# Перезапустить таймер
restart_timer() {
    local timer_name=$1
    check_timer "$timer_name"
    local timer_file=${TIMERS[$timer_name]}
    
    print_info "Перезапуск таймера $timer_name..."
    
    systemctl restart "$timer_file"
    
    print_info "Таймер $timer_name перезапущен"
}

# Показать расписание
show_schedule() {
    print_info "Расписание таймеров:"
    echo
    
    for timer_name in "${!TIMERS[@]}"; do
        local timer_file=${TIMERS[$timer_name]}
        echo "=== $timer_name ==="
        
        if [[ -f "$TIMERS_DIR/$timer_file" ]]; then
            grep -A 5 "\[Timer\]" "$TIMERS_DIR/$timer_file" | grep -v "^--$"
        fi
        echo
    done
}

# Показать логи таймера
show_logs() {
    local timer_name=$1
    check_timer "$timer_name"
    local service_file=${TIMERS[$timer_name]%.timer}.service
    
    print_info "Логи таймера $timer_name (последние 50 строк):"
    
    journalctl -u "$service_file" -n 50 --no-pager
}

# Показать справку
show_help() {
    echo "Управление systemd таймерами интеграций"
    echo
    echo "Использование: $0 [COMMAND] [TIMER_NAME]"
    echo
    echo "COMMANDS:"
    echo "  install       Установить все таймеры в systemd"
    echo "  status        Показать статус всех таймеров"
    echo "  enable TIMER Включить конкретный таймер"
    echo "  disable TIMER Отключить конкретный таймер"
    echo "  start TIMER   Запустить конкретный таймер"
    echo "  stop TIMER    Остановить конкретный таймер"
    echo "  restart TIMER Перезапустить конкретный таймер"
    echo "  logs TIMER    Показать логи конкретного таймера"
    echo "  schedule      Показать расписание всех таймеров"
    echo "  help          Показать эту справку"
    echo
    echo "TIMER_NAME: ${!TIMERS[*]}"
    echo
    echo "Примеры:"
    echo "  $0 install                    # Установить все таймеры"
    echo "  $0 enable qtickets            # Включить QTickets таймер"
    echo "  $0 status vk_ads              # Показать статус VK Ads таймера"
    echo "  $0 logs qtickets              # Показать логи QTickets"
}

# Основная логика
main() {
    case "${1:-help}" in
        install)
            check_root
            install_timers
            ;;
        status)
            if [[ -n "${2:-}" ]]; then
                show_timer_status "$2"
            else
                show_status
            fi
            ;;
        enable)
            check_root
            enable_timer "$2"
            ;;
        disable)
            check_root
            disable_timer "$2"
            ;;
        start)
            check_root
            start_timer "$2"
            ;;
        stop)
            check_root
            stop_timer "$2"
            ;;
        restart)
            check_root
            restart_timer "$2"
            ;;
        logs)
            show_logs "$2"
            ;;
        schedule)
            show_schedule
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Неизвестная команда: $1"
            show_help
            exit 1
            ;;
    esac
}

# Запуск
main "$@"