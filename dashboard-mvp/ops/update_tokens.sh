#!/bin/bash

# Скрипт для обновления токенов в файлах конфигурации
# Использование: bash ops/update_tokens.sh

echo "=== Обновление токенов ==="

# Запрос токена VK Ads
echo "Получение токена VK Ads..."
read -p "Введите VK API токен: " VK_TOKEN
read -p "Введите ID кабинетов VK через запятую: " VK_ACCOUNTS

# Обновление файла .env.vk_ads
cat > secrets/.env.vk_ads << EOF
# VK Ads
VK_API_TOKEN=$VK_TOKEN
VK_CLIENT_EMAIL=lazur.estate@yandex.ru
VK_ACCOUNT_IDS=$VK_ACCOUNTS
VK_RATE_LIMIT_QPS=3
TZ=Europe/Moscow
EOF

echo "✓ Обновлен secrets/.env.vk_ads"

# Запрос токена Яндекс.Директ
echo ""
echo "Получение токена Яндекс.Директ..."
read -p "Введите OAuth токен Яндекс.Директ: " DIRECT_TOKEN

# Обновление файла .env.direct
cat > secrets/.env.direct << EOF
# Яндекс.Директ
YANDEX_DIRECT_LOGIN=ads-irsshow@yandex.ru
YANDEX_DIRECT_PASSWORD=irs20show24
DIRECT_OAUTH_TOKEN=$DIRECT_TOKEN
DIRECT_CLIENT_LOGIN=ads-irsshow@yandex.ru
DIRECT_API_BASE=https://api.direct.yandex.com/json/v5/reports
DIRECT_REPORT_STATAUCTION=false
TZ=Europe/Moscow
EOF

echo "✓ Обновлен secrets/.env.direct"

# Установка прав доступа
chmod 600 secrets/.env.vk_ads
chmod 600 secrets/.env.direct

echo ""
echo "=== Токены обновлены ==="
echo "Теперь можно выполнить загрузку данных:"
echo "bash ops/backfill_data.sh"