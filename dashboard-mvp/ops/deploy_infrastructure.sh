#!/bin/bash

# Скрипт развертывания инфраструктуры на VPS для Zakaz Dashboard
# Использование: bash ops/deploy_infrastructure.sh

set -e

echo "=== Начало развертывания инфраструктуры Zakaz Dashboard ==="

# Проверка наличия Docker и Docker Compose
if ! command -v docker &> /dev/null; then
    echo "Docker не установлен. Устанавливаем..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose не установлен. Устанавливаем..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Создание необходимых директорий
echo "Создание директорий для данных..."
mkdir -p infra/clickhouse/data
mkdir -p infra/clickhouse/logs
mkdir -p infra/clickhouse/caddy_data
mkdir -p logs

# Установка прав доступа к секретам
echo "Настройка прав доступа к секретам..."
chmod 700 secrets/
chmod 600 secrets/.env.*

# Переход в директорию с ClickHouse
cd infra/clickhouse

# Загрузка образов и запуск контейнеров
echo "Запуск ClickHouse и Caddy..."
docker-compose pull
docker-compose up -d

# Ожидание запуска ClickHouse
echo "Ожидание запуска ClickHouse..."
sleep 30

# Проверка работоспособности ClickHouse
echo "Проверка работоспособности ClickHouse..."
docker exec ch-zakaz clickhouse-client -q "SELECT version()"

# Инициализация базы данных и таблиц
echo "Инициализация базы данных и таблиц..."
docker exec -i ch-zakaz clickhouse-client --user=admin --password=AdminMin2024!Strong#Pass < init.sql

# Проверка доступности через HTTPS
echo "Проверка доступности через HTTPS..."
sleep 10
DOMAIN="bi.zakaz-dashboard.ru"
echo "Проверка доступности: https://$DOMAIN/ping"
curl -I https://$DOMAIN/ping || echo "ВНИМАНИЕ: HTTPS может быть недоступен до настройки DNS"

echo "=== Развертывание инфраструктуры завершено ==="
echo ""
echo "Следующие шаги:"
echo "1. Убедитесь, что DNS A-запись для $DOMAIN указывает на этот сервер"
echo "2. Выпустите токены для VK Ads и Яндекс.Директ"
echo "3. Заполните секреты в secrets/.env.vk_ads и secrets/.env.direct"
echo "4. Выполните backfill данных за 90 дней"