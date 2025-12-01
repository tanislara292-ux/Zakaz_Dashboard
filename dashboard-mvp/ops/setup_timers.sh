#!/bin/bash

# Скрипт для настройки systemd таймеров
# Использование: sudo bash ops/setup_timers.sh

set -e

echo "=== Настройка systemd таймеров для Zakaz Dashboard ==="

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "Этот скрипт необходимо запускать с правами root"
    echo "Используйте: sudo bash ops/setup_timers.sh"
    exit 1
fi

# Копирование файлов systemd
echo "Копирование файлов systemd..."
cp ops/systemd/*.service /etc/systemd/system/
cp ops/systemd/*.timer /etc/systemd/system/

# Перезагрузка systemd
echo "Перезагрузка systemd..."
systemctl daemon-reload

# Создание пользователя etl при необходимости
if ! id "etl" &>/dev/null; then
    echo "Создание пользователя etl..."
    useradd -r -s /bin/false etl
    usermod -aG docker etl
fi

# Установка прав на директорию проекта
echo "Настройка прав доступа..."
chown -R etl:etl /opt/zakaz_dashboard 2>/dev/null || echo "Предупреждение: не удалось установить права на /opt/zakaz_dashboard"

# Включение таймеров
echo "Включение таймеров..."

# QTickets - каждые 30 минут
systemctl enable --now qtickets.timer
echo "✓ Включен таймер qtickets (каждые 30 минут)"

# VK Ads - ежедневно в 00:00 MSK
systemctl enable --now vk_ads.timer
echo "✓ Включен таймер vk_ads (ежедневно в 00:00 MSK)"

# Яндекс.Директ - ежедневно в 00:10 MSK
systemctl enable --now direct.timer
echo "✓ Включен таймер direct (ежедневно в 00:10 MSK)"

# Gmail - отключен по умолчанию (резервный канал)
systemctl disable gmail_ingest.timer 2>/dev/null || echo "✓ Таймер gmail_ingest уже отключен"

# Алерты - каждые 2 часа
systemctl enable --now alerts.timer
echo "✓ Включен таймер alerts (каждые 2 часа)"

# Healthcheck сервер - непрерывная работа
systemctl enable --now healthcheck.service
echo "✓ Включен сервис healthcheck"

# Smoke тесты - ежедневно в 06:00 MSK
systemctl enable --now smoke_test_integrations.timer
echo "✓ Включен таймер smoke_test_integrations (ежедневно в 06:00 MSK)"

# Проверка статуса таймеров
echo ""
echo "=== Статус таймеров ==="
systemctl list-timers | grep -E 'qtickets|vk_ads|direct|alerts|smoke_test_integrations'

# Проверка статуса сервисов
echo ""
echo "=== Статус сервисов ==="
systemctl status healthcheck.service --no-pager -l

echo ""
echo "=== Настройка таймеров завершена ==="
echo ""
echo "Для просмотра логов используйте:"
echo "  journalctl -u qtickets.service -f"
echo "  journalctl -u vk_ads.service -f"
echo "  journalctl -u direct.service -f"
echo "  journalctl -u alerts.service -f"
echo "  journalctl -u healthcheck.service -f"
echo ""
echo "Для ручного запуска:"
echo "  systemctl start qtickets.service"
echo "  systemctl start vk_ads.service"
echo "  systemctl start direct.service"