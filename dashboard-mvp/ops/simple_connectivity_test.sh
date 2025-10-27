#!/bin/bash

# Простой скрипт проверки доступности ClickHouse для DataLens
# Использование: bash ops/simple_connectivity_test.sh

echo "=== Проверка доступности ClickHouse для DataLens ==="
echo "Дата: $(date)"
echo ""

# Параметры подключения
HOST="bi.zakaz-dashboard.ru"
PORT="443"
DATABASE="zakaz"
USERNAME="datalens_reader"
PASSWORD="DataLens2024!Strong#Pass"

echo "Параметры подключения:"
echo "  Хост: $HOST"
echo "  Порт: $PORT"
echo "  База данных: $DATABASE"
echo "  Пользователь: $USERNAME"
echo ""

# Тест 1: Проверка доступности хоста
echo "1. Проверка доступности хоста..."
if ping -c 1 $HOST >/dev/null 2>&1; then
    echo "✅ Хост $HOST доступен"
else
    echo "❌ Хост $HOST недоступен"
    echo "   Проверьте DNS и сетевое соединение"
fi
echo ""

# Тест 2: Проверка HTTPS доступности
echo "2. Проверка HTTPS доступности..."
if curl -s -k --connect-timeout 10 "https://$HOST:$PORT/?query=SELECT%201" >/dev/null 2>&1; then
    echo "✅ HTTPS доступ к ClickHouse работает"
    
    # Тестовый запрос с аутентификацией
    echo "2.1. Проверка аутентификации..."
    RESPONSE=$(curl -s -k --connect-timeout 10 "https://$HOST:$PORT/?query=SELECT%201&user=$USERNAME&password=$PASSWORD&database=$DATABASE" 2>/dev/null)
    
    if [[ "$RESPONSE" == *"1"* ]]; then
        echo "✅ Аутентификация успешна"
    else
        echo "❌ Ошибка аутентификации"
        echo "   Ответ: $RESPONSE"
    fi
else
    echo "❌ HTTPS доступ к ClickHouse не работает"
    echo "   Проверьте настройки реверс-прокси и SSL сертификат"
fi
echo ""

# Тест 3: Проверка доступа к данным (если аутентификация прошла)
if [[ "$RESPONSE" == *"1"* ]]; then
    echo "3. Проверка доступа к данным..."
    
    # Проверка таблицы продаж
    echo "3.1. Проверка таблицы продаж..."
    SALES_COUNT=$(curl -s -k --connect-timeout 10 "https://$HOST:$PORT/?query=SELECT%20count()%20FROM%20zakaz.v_sales_latest&user=$USERNAME&password=$PASSWORD&database=$DATABASE" 2>/dev/null)
    if [[ -n "$SALES_COUNT" ]]; then
        echo "✅ Таблица продаж доступна, записей: $SALES_COUNT"
    else
        echo "❌ Таблица продаж недоступна"
    fi
    
    # Проверка таблицы маркетинга
    echo "3.2. Проверка таблицы маркетинга..."
    MARKETING_COUNT=$(curl -s -k --connect-timeout 10 "https://$HOST:$PORT/?query=SELECT%20count()%20FROM%20zakaz.v_marketing_daily&user=$USERNAME&password=$PASSWORD&database=$DATABASE" 2>/dev/null)
    if [[ -n "$MARKETING_COUNT" ]]; then
        echo "✅ Таблица маркетинга доступна, записей: $MARKETING_COUNT"
    else
        echo "❌ Таблица маркетинга недоступна"
    fi
    
    # Проверка свежести данных
    echo "3.3. Проверка свежести данных..."
    LATEST_DATE=$(curl -s -k --connect-timeout 10 "https://$HOST:$PORT/?query=SELECT%20max(event_date)%20FROM%20zakaz.v_sales_latest&user=$USERNAME&password=$PASSWORD&database=$DATABASE" 2>/dev/null)
    if [[ -n "$LATEST_DATE" ]]; then
        echo "✅ Последняя дата продаж: $LATEST_DATE"
    else
        echo "❌ Не удалось получить свежесть данных"
    fi
fi
echo ""

# Тест 4: Рекомендации для DataLens
echo "4. Рекомендации для настройки DataLens:"
echo "   Хост: $HOST"
echo "   Порт: $PORT"
echo "   База данных: $DATABASE"
echo "   Имя пользователя: $USERNAME"
echo "   Пароль: $PASSWORD"
echo "   Использовать HTTPS: Да"
echo ""

if [[ "$RESPONSE" == *"1"* ]]; then
    echo "🎉 Система готова к настройке DataLens!"
    echo ""
    echo "Следующие шаги:"
    echo "1. Войдите в DataLens: https://datalens.yandex.ru/"
    echo "2. Создайте подключение ClickHouse с указанными параметрами"
    echo "3. Создайте источники данных на основе представлений:"
    echo "   - zakaz.v_sales_latest"
    echo "   - zakaz.v_marketing_daily"
    echo "   - zakaz.v_sales_14d"
else
    echo "❌ Система не готова к настройке DataLens"
    echo "   Необходимо решить проблемы с подключением к ClickHouse"
fi

echo ""
echo "=== Проверка завершена ==="