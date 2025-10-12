#!/bin/bash

# Полный скрипт развертывания Zakaz Dashboard
# Использование: sudo bash ops/full_deployment.sh

set -e

echo "=== Полное развертывание Zakaz Dashboard ==="
echo "Версия: 1.0.0"
echo "Дата: $(date +%Y-%m-%d)"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "Этот скрипт необходимо запускать с правами root"
    echo "Используйте: sudo bash ops/full_deployment.sh"
    exit 1
fi

# Шаг 1: Развертывание инфраструктуры
echo "=== Шаг 1: Развертывание инфраструктуры ==="
bash ops/deploy_infrastructure.sh

# Шаг 2: Настройка таймеров
echo ""
echo "=== Шаг 2: Настройка таймеров ==="
bash ops/setup_timers.sh

# Шаг 3: Проверка системы
echo ""
echo "=== Шаг 3: Проверка системы ==="
bash ops/system_check.sh

# Шаг 4: Обновление токенов
echo ""
echo "=== Шаг 4: Обновление токенов ==="
echo "Учетные данные находятся в secrets/ACCESS.md"
echo ""
read -p "Обновить токены сейчас? (y/n): " UPDATE_TOKENS

if [ "$UPDATE_TOKENS" = "y" ] || [ "$UPDATE_TOKENS" = "Y" ]; then
    bash ops/update_tokens.sh
else
    echo "Пропуск обновления токенов"
    echo "Вы можете обновить их позже с помощью: bash ops/update_tokens.sh"
fi

# Шаг 5: Загрузка данных
echo ""
echo "=== Шаг 5: Загрузка данных ==="
read -p "Выполнить загрузку исторических данных? (требуются токены) (y/n): " LOAD_DATA

if [ "$LOAD_DATA" = "y" ] || [ "$LOAD_DATA" = "Y" ]; then
    bash ops/backfill_data.sh
else
    echo "Пропуск загрузки данных"
    echo "Вы можете загрузить данные позже: bash ops/backfill_data.sh"
fi

# Шаг 6: Инструкции по следующими шагам
echo ""
echo "=== Следующие шаги ==="
echo "1. Настройте DataLens:"
echo "   - См. инструкцию в ops/DATALENS_SETUP.md"
echo "   - Создайте подключение к ClickHouse (bi.zakaz-dashboard.ru)"
echo "   - Пользователь: datalens_reader / DataLens2024!Strong#Pass"
echo "   - Создайте дашборд"
echo ""
echo "2. Включите бэкапы:"
echo "   sudo bash ops/backup_full.sh"
echo ""
echo "3. Проверьте работу алертов:"
echo "   - Проверьте email на ads-irsshow@yandex.ru"
echo ""
echo "4. Удалите или защитите файл с учетными данными:"
echo "   chmod 600 secrets/ACCESS.md"
echo ""
echo "=== Развертывание завершено ==="
echo ""
echo "Полная документация:"
echo "- ops/HANDOVER_PACKAGE.md - пакет передачи проекта"
echo "- ops/VPS_DEPLOYMENT_INSTRUCTIONS.md - инструкция по развертыванию"
echo "- ops/TOKEN_GUIDE.md - инструкция по получению токенов"
echo "- ops/DATALENS_SETUP.md - инструкция по настройке DataLens"
echo ""
echo "Полезные команды:"
echo "- Проверка системы: bash ops/system_check.sh"
echo "- Просмотр логов: journalctl -u qtickets.service -f"
echo "- Перезапуск таймера: systemctl restart qtickets.service"
echo "- Статус таймеров: systemctl list-timers"