#!/bin/bash

# Скрипт для запуска smoke-тестов системы интеграций
# Использование: ./run_smoke_test.sh [options]

set -e

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

# Проверка зависимостей
check_dependencies() {
    print_info "Проверка зависимостей..."
    
    # Проверка Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 не найден"
        exit 1
    fi
    
    # Проверка ClickHouse
    if ! curl -s http://localhost:8123/ping &> /dev/null; then
        print_warn "ClickHouse недоступен на localhost:8123"
        echo "  Убедитесь, что ClickHouse запущен"
    fi
    
    # Проверка переменных окружения
    if [[ ! -f "secrets/.env.ch" ]]; then
        print_error "Файл secrets/.env.ch не найден"
        echo "  Создайте файл на основе configs/.env.ch.sample"
        exit 1
    fi
    
    print_info "Зависимости проверены"
}

# Запуск smoke-тестов
run_smoke_test() {
    local output_file=""
    local verbose=""
    
    # Разбор аргументов
    while [[ $# -gt 0 ]]; do
        case $1 in
            --output|-o)
                output_file="$2"
                shift 2
                ;;
            --verbose|-v)
                verbose="--verbose"
                shift
                ;;
            *)
                print_error "Неизвестный аргумент: $1"
                echo "Использование: $0 [--output FILE] [--verbose]"
                exit 1
                ;;
        esac
    done
    
    print_info "Запуск smoke-тестов системы интеграций..."
    
    # Создание директории для результатов
    mkdir -p logs
    
    # Запуск smoke-тестов
    local cmd="python3 ops/smoke_test_integrations.py --env secrets/.env.ch"
    
    if [[ -n "$verbose" ]]; then
        cmd="$cmd $verbose"
    fi
    
    if [[ -n "$output_file" ]]; then
        cmd="$cmd --output $output_file"
        print_info "Результаты будут сохранены в $output_file"
    fi
    
    # Выполнение тестов
    local exit_code=0
    if eval "$cmd"; then
        print_info "Smoke-тесты успешно завершены"
        
        # Если указан файл вывода, выводим краткую статистику
        if [[ -n "$output_file" && -f "$output_file" ]]; then
            print_info "Статистика:"
            python3 -c "
import json
with open('$output_file') as f:
    data = json.load(f)
    status = data['overall_status']
    tests = data['tests']
    print(f'  Статус: {status}')
    print(f'  Тестов: {tests[\"total\"]} (пройдено: {tests[\"passed\"]}, провалено: {tests[\"failed\"]}, предупреждений: {tests[\"warnings\"]})')
    print(f'  Длительность: {data[\"duration_seconds\"]} сек')
"
        fi
    else
        print_error "Smoke-тесты завершены с ошибками"
        exit_code=1
    fi
    
    return $exit_code
}

# Запуск smoke-тестов и сохранение результатов
run_smoke_test_with_results() {
    local output_file="logs/smoke_test_$(date +%Y%m%d_%H%M%S).json"
    
    print_info "Запуск smoke-тестов с сохранением результатов..."
    
    # Создание директории для результатов
    mkdir -p logs
    
    # Запуск smoke-тестов
    if python3 ops/smoke_test_integrations.py --env secrets/.env.ch --output "$output_file"; then
        print_info "Smoke-тесты успешно завершены"
        
        # Вывод статистики
        python3 -c "
import json
with open('$output_file') as f:
    data = json.load(f)
    status = data['overall_status']
    tests = data['tests']
    print(f'  Статус: {status}')
    print(f'  Тестов: {tests[\"total\"]} (пройдено: {tests[\"passed\"]}, провалено: {tests[\"failed\"]}, предупреждений: {tests[\"warnings\"]})')
    print(f'  Длительность: {data[\"duration_seconds\"]} сек')
    print(f'  Результаты: $output_file')
"
        
        # Проверка статуса
        if [[ "$(python3 -c "import json; data=json.load(open('$output_file')); print(data['overall_status'])")" != "ok" ]]; then
            print_error "Обнаружены проблемы в системе"
            return 1
        fi
    else
        print_error "Smoke-тесты завершены с ошибками"
        return 1
    fi
}

# Запуск smoke-тестов для CI/CD
run_smoke_test_ci() {
    local output_file="logs/smoke_test_ci_$(date +%Y%m%d_%H%M%S).json"
    
    print_info "Запуск smoke-тестов для CI/CD..."
    
    # Создание директории для результатов
    mkdir -p logs
    
    # Запуск smoke-тестов
    if python3 ops/smoke_test_integrations.py --env secrets/.env.ch --output "$output_file" --verbose; then
        print_info "Smoke-тесты успешно завершены"
        
        # Вывод статистики
        python3 -c "
import json
with open('$output_file') as f:
    data = json.load(f)
    status = data['overall_status']
    tests = data['tests']
    print(f'Статус: {status}')
    print(f'Тестов: {tests[\"total\"]} (пройдено: {tests[\"passed\"]}, провалено: {tests[\"failed\"]}, предупреждений: {tests[\"warnings\"]})')
    print(f'Длительность: {data[\"duration_seconds\"]} сек')
"
        
        # Проверка статуса
        if [[ "$(python3 -c "import json; data=json.load(open('$output_file')); print(data['overall_status'])")" != "ok" ]]; then
            print_error "Обнаружены проблемы в системе"
            return 1
        fi
    else
        print_error "Smoke-тесты завершены с ошибками"
        return 1
    fi
}

# Проверка здоровья системы
check_health() {
    print_info "Проверка здоровья системы..."
    
    # Проверка healthcheck сервера
    if curl -s http://localhost:8080/healthz >/dev/null; then
        print_info "Healthcheck сервер доступен"
        
        # Получение статуса
        local status=$(curl -s http://localhost:8080/healthz | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "error")
        
        if [[ "$status" == "ok" ]]; then
            print_info "Система работает нормально"
        else
            print_warn "Обнаружены проблемы в системе"
        fi
    else
        print_error "Healthcheck сервер недоступен"
        return 1
    fi
    
    return 0
}

# Показать справку
show_help() {
    echo "Smoke-тестирование системы интеграций"
    echo
    echo "Использование: $0 [COMMAND]"
    echo
    echo "COMMANDS:"
    echo "  run           Запуск smoke-тестов"
    echo "  run-with-results Запуск smoke-тестов с сохранением результатов"
    echo "  ci            Запуск smoke-тестов для CI/CD (с выводом статистики)"
    echo "  health        Проверка здоровья системы"
    echo "  help          Показать эту справку"
    echo
    echo "Примеры:"
    echo "  $0 run                    # Запуск smoke-тестов"
    echo "  $0 run-with-results        # Запуск с сохранением результатов"
    echo "  $0 health                 # Проверка здоровья системы"
}

# Основная логика
main() {
    case "${1:-help}" in
        run)
            check_dependencies
            run_smoke_test
            ;;
        run-with-results)
            check_dependencies
            run_smoke_test_with_results
            ;;
        ci)
            check_dependencies
            run_smoke_test_ci
            ;;
        health)
            check_health
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