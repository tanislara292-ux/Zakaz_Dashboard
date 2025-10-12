#!/bin/bash

# Скрипт быстрого развертывания почтового дашборда
# Gmail → ClickHouse → DataLens

set -e

echo "🚀 Развертывание почтового дашборда..."

# Проверяем наличие необходимых компонентов
check_requirements() {
    echo "📋 Проверка требований..."
    
    if ! command -v clickhouse-client &> /dev/null; then
        echo "❌ clickhouse-client не найден"
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        echo "❌ python3 не найден"
        exit 1
    fi
    
    echo "✅ Требования проверены"
}

# Инициализация ClickHouse
init_clickhouse() {
    echo "🗄️ Инициализация ClickHouse..."
    
    # Выполняем DDL
    clickhouse-client --multiquery < infra/clickhouse/init_mail.sql
    
    if [ $? -eq 0 ]; then
        echo "✅ Таблицы ClickHouse созданы"
    else
        echo "❌ Ошибка при создании таблиц ClickHouse"
        exit 1
    fi
}

# Настройка Python окружения
setup_python_env() {
    echo "🐍 Настройка Python окружения..."
    
    cd mail-python
    
    # Создаем виртуальное окружение если нет
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        echo "✅ Виртуальное окружение создано"
    fi
    
    # Активируем и устанавливаем зависимости
    source .venv/bin/activate
    pip install -r requirements.txt > /dev/null 2>&1
    
    echo "✅ Зависимости Python установлены"
    
    # Создаем .env если нет
    if [ ! -f ".env" ]; then
        cp .env.sample .env
        echo "⚠️  Создан .env файл - отредактируйте его с вашими настройками"
    fi
    
    cd ..
}

# Настройка systemd сервисов
setup_systemd() {
    echo "⚙️ Настройка systemd сервисов..."
    
    # Копируем файлы systemd
    sudo cp infra/systemd/gmail-ingest.service /etc/systemd/system/
    sudo cp infra/systemd/gmail-ingest.timer /etc/systemd/system/
    
    # Перезагружаем systemd
    sudo systemctl daemon-reload
    
    echo "✅ systemd сервисы настроены"
}

# Проверка работоспособности
verify_setup() {
    echo "🔍 Проверка развертывания..."
    
    # Проверяем таблицы
    TABLES=$(clickhouse-client --query "SHOW TABLES FROM zakaz LIKE '%sales%'" 2>/dev/null)
    if [[ $TABLES == *"stg_mail_sales_raw"* ]]; then
        echo "✅ Таблицы ClickHouse созданы"
    else
        echo "❌ Таблицы ClickHouse не найдены"
        return 1
    fi
    
    # Проверяем Python окружение
    cd mail-python
    if [ -d ".venv" ] && [ -f ".env" ]; then
        echo "✅ Python окружение настроено"
    else
        echo "❌ Python окружение не настроено"
        return 1
    fi
    cd ..
    
    echo "✅ Развертывание успешно завершено"
}

# Инструкции по следующем шагам
next_steps() {
    echo ""
    echo "🎉 Развертывание завершено! Следующие шаги:"
    echo ""
    echo "1. 📧 Настройте Gmail API:"
    echo "   - Перейдите в Google Cloud Console"
    echo "   - Включите Gmail API"
    echo "   - Создайте OAuth 2.0 Client ID"
    echo "   - Скачайте credentials.json в mail-python/secrets/gmail/"
    echo ""
    echo "2. ⚙️ Отредактируйте конфигурацию:"
    echo "   - mail-python/.env (настройки ClickHouse и Gmail)"
    echo ""
    echo "3. 🧪 Протестируйте инжестор:"
    echo "   cd mail-python"
    echo "   source .venv/bin/activate"
    echo "   python gmail_ingest.py --dry-run --limit 3"
    echo ""
    echo "4. 🚀 Включите автоматизацию:"
    echo "   sudo systemctl enable --now gmail-ingest.timer"
    echo "   sudo systemctl list-timers | grep gmail-ingest"
    echo ""
    echo "5. 📊 Настройте DataLens:"
    echo "   - Следуйте инструкции в docs/DATALENS_MAIL_SETUP.md"
    echo ""
    echo "📚 Документация:"
    echo "   - README_MAIL_DASHBOARD.md - полное руководство"
    echo "   - mail-python/README.md - детали инжестора"
    echo "   - docs/DATALENS_MAIL_SETUP.md - настройка DataLens"
}

# Основной процесс
main() {
    echo "🏁 Начало развертывания почтового дашборда..."
    echo ""
    
    check_requirements
    init_clickhouse
    setup_python_env
    setup_systemd
    verify_setup
    next_steps
    
    echo ""
    echo "✨ Готово!"
}

# Запуск
main "$@"