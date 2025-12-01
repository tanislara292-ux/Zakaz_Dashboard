#!/bin/bash

# Manage Zakaz Dashboard systemd timers/services.
# Usage: ./manage_timers.sh [start|stop|restart|status|enable|disable|logs|schedule|install] [timer_name]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMERS_DIR="$SCRIPT_DIR"

# Map logical names to timer unit files
declare -A TIMERS=(
    ["qtickets"]="qtickets.timer"
    ["qtickets_sheets"]="qtickets_sheets.timer"
    ["qtickets_api"]="qtickets_api.timer"
    ["vk_ads"]="vk_ads.timer"
    ["direct"]="direct.timer"
    ["gmail"]="gmail_ingest.timer"
    ["alerts"]="alerts.timer"
)

# Additional standalone units to copy (not timers)
EXTRA_UNITS=(
    "healthcheck.service"
)

print_info() { echo -e "\033[0;32m[INFO]\033[0m $1"; }
print_warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
print_error(){ echo -e "\033[0;31m[ERROR]\033[0m $1"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Run as root (sudo) to manage systemd units."
        exit 1
    fi
}

check_timer() {
    local timer_name=$1
    local timer_file=${TIMERS[$timer_name]:-}
    if [[ -z "$timer_file" ]]; then
        print_error "Unknown timer: $timer_name"
        print_info "Available timers: ${!TIMERS[*]}"
        exit 1
    fi
    if [[ ! -f "$TIMERS_DIR/$timer_file" ]]; then
        print_error "Timer file not found: $TIMERS_DIR/$timer_file"
        exit 1
    fi
}

install_timers() {
    print_info "Installing timer/service units into systemd..."

    for timer_file in "${TIMERS[@]}"; do
        if [[ -f "${TIMERS_DIR}/${timer_file}" ]]; then
            cp "${TIMERS_DIR}/${timer_file}" "/etc/systemd/system/"
            print_info "Installed: ${timer_file}"

            service_file="${timer_file%.timer}.service"
            if [[ -f "${TIMERS_DIR}/${service_file}" ]]; then
                cp "${TIMERS_DIR}/${service_file}" "/etc/systemd/system/"
                print_info "Installed: ${service_file}"
            fi
        fi
    done

    for unit_file in "${EXTRA_UNITS[@]}"; do
        if [[ -f "${TIMERS_DIR}/${unit_file}" ]]; then
            cp "${TIMERS_DIR}/${unit_file}" "/etc/systemd/system/"
            print_info "Installed: ${unit_file}"
        fi
    done

    systemctl daemon-reload
    print_info "systemd daemon reloaded."
}

show_status() {
    print_info "Timer status:"
    echo
    for timer_name in "${!TIMERS[@]}"; do
        local timer_file=${TIMERS[$timer_name]}
        echo "=== $timer_name ($timer_file) ==="
        if systemctl list-timers --all | grep -q "$timer_file"; then
            systemctl status "$timer_file" --no-pager -l
        else
            echo "Timer not installed"
        fi
        echo
    done
}

show_timer_status() {
    local timer_name=$1
    check_timer "$timer_name"
    local timer_file=${TIMERS[$timer_name]}
    print_info "Status for $timer_name ($timer_file):"
    if systemctl list-timers --all | grep -q "$timer_file"; then
        systemctl status "$timer_file" --no-pager -l
    else
        print_warn "Timer not installed"
    fi
}

enable_timer()   { check_timer "$1"; print_info "Enabling $1"; systemctl enable "${TIMERS[$1]}"; systemctl start "${TIMERS[$1]}"; }
disable_timer()  { check_timer "$1"; print_info "Disabling $1"; systemctl stop "${TIMERS[$1]}" 2>/dev/null || true; systemctl disable "${TIMERS[$1]}"; }
start_timer()    { check_timer "$1"; print_info "Starting $1"; systemctl start "${TIMERS[$1]}"; }
stop_timer()     { check_timer "$1"; print_info "Stopping $1"; systemctl stop "${TIMERS[$1]}"; }
restart_timer()  { check_timer "$1"; print_info "Restarting $1"; systemctl restart "${TIMERS[$1]}"; }

show_logs() {
    local timer_name=$1
    check_timer "$timer_name"
    local service_file=${TIMERS[$timer_name]%.timer}.service
    print_info "Logs for $timer_name (last 50 lines):"
    journalctl -u "$service_file" -n 50 --no-pager
}

show_schedule() {
    print_info "Timer schedules:"
    echo
    for timer_name in "${!TIMERS[@]}"; do
        local timer_file=${TIMERS[$timer_name]}
        echo "=== $timer_name ==="
        if [[ -f "$TIMERS_DIR/$timer_file" ]]; then
            grep -A 5 "\\[Timer\\]" "$TIMERS_DIR/$timer_file" | grep -v '^--$'
        fi
        echo
    done
}

show_help() {
    cat <<EOF
Manage Zakaz Dashboard systemd timers

Usage: $0 [COMMAND] [TIMER_NAME]

Commands:
  install        Copy units to /etc/systemd/system and reload daemon
  status         Show status for all timers (or specific if TIMER_NAME provided)
  enable TIMER   Enable + start timer
  disable TIMER  Disable + stop timer
  start TIMER    Start timer
  stop TIMER     Stop timer
  restart TIMER  Restart timer
  logs TIMER     Show last 50 log lines for the service behind the timer
  schedule       Show configured schedules from unit files
  help           Show this message

Timers: ${!TIMERS[*]}

Examples:
  sudo $0 install
  sudo $0 enable qtickets
  $0 status vk_ads
  $0 logs qtickets
EOF
}

main() {
    case "${1:-help}" in
        install) check_root; install_timers ;;
        status)  if [[ -n "${2:-}" ]]; then show_timer_status "$2"; else show_status; fi ;;
        enable)  check_root; enable_timer "$2" ;;
        disable) check_root; disable_timer "$2" ;;
        start)   check_root; start_timer "$2" ;;
        stop)    check_root; stop_timer "$2" ;;
        restart) check_root; restart_timer "$2" ;;
        logs)    show_logs "$2" ;;
        schedule)show_schedule ;;
        help|--help|-h) show_help ;;
        *) print_error "Unknown command: $1"; show_help; exit 1 ;;
    esac
}

main "$@"
