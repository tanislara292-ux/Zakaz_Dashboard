#!/bin/bash

# Скрипт для инициализации таблиц ClickHouse для почтового инжестора

echo "Инициализация таблиц ClickHouse для почтового инжестора..."

# Проверяем доступность ClickHouse
if ! clickhouse-client --query "SELECT 1" > /dev/null 2>&1; then
    echo "Ошибка: не удалось подключиться к ClickHouse"
    exit 1
fi

# Выполняем DDL
clickhouse-client --multiquery < ../infra/clickhouse/init_mail.sql

if [ $? -eq 0 ]; then
    echo "✅ Таблицы успешно созданы"
else
    echo "❌ Ошибка при создании таблиц"
    exit 1
fi

# Проверяем создание таблиц
echo "Проверка создания таблиц..."
clickhouse-client --query "SHOW TABLES FROM zakaz LIKE 'stg_mail_sales_raw'"
clickhouse-client --query "SHOW TABLES FROM zakaz LIKE 'v_sales_latest'"
clickhouse-client --query "SHOW TABLES FROM zakaz LIKE 'v_sales_14d'"

echo "Готово!"