# Инструкция по развертыванию на VPS

## Подготовительные шаги

1. Подключитесь к VPS по SSH:
   ```bash
   ssh ads-irsshow@yandex.ru@<VPS_IP>
   ```

2. Клонируйте репозиторий:
   ```bash
   git clone <repository_url> zakaz_dashboard
   cd zakaz_dashboard
   ```

3. Сделайте скрипт развертывания исполняемым:
   ```bash
   chmod +x ops/deploy_infrastructure.sh
   ```

## Развертывание

1. Запустите скрипт развертывания:
   ```bash
   bash ops/deploy_infrastructure.sh
   ```

2. После завершения развертывания проверьте статус контейнеров:
   ```bash
   cd infra/clickhouse
   docker-compose ps
   ```

## Настройка DNS

1. Убедитесь, что A-запись для `bi.zakaz-dashboard.ru` указывает на IP-адрес VPS

2. Проверьте доступность:
   ```bash
   curl -I https://bi.zakaz-dashboard.ru/ping
   ```

## Выпуск токенов

### VK Ads

1. Войдите в аккаунт VK Ads: `lazur.estate@yandex.ru`
2. Создайте API-токен со статистикой
3. Добавьте токен в `secrets/.env.vk_ads`
4. Получите ID кабинетов и добавьте их в `VK_ACCOUNT_IDS`

### Яндекс.Директ

1. Войдите в аккаунт Яндекс.Директ: `ads-irsshow@yandex.ru` / `irs20show24`
2. Получите OAuth-токен для API Директа
3. Добавьте токен в `secrets/.env.direct`

## Backfill данных

После настройки токенов выполните:

```bash
# QTickets
python -m integrations.qtickets.loader --days 90 --verbose --envfile secrets/.env.qtickets --ch-env secrets/.env.ch

# VK Ads
python -m integrations.vk_ads.loader --days 90 --verbose --envfile secrets/.env.vk_ads --ch-env secrets/.env.ch

# Яндекс.Директ
python -m integrations.direct.loader --days 90 --verbose --envfile secrets/.env.direct --ch-env secrets/.env.ch
```

## Проверка данных

Проверьте наличие данных в ClickHouse:

```sql
SELECT count() FROM zakaz.v_sales_latest WHERE event_date >= today()-7;
SELECT sum(spend_total) FROM zakaz.v_marketing_daily WHERE d >= today()-7;
SELECT max(event_date) FROM zakaz.v_sales_latest;
SELECT max(d) FROM zakaz.v_marketing_daily;
```

## Настройка автоматизации

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qtickets.timer
sudo systemctl enable --now vk_ads.timer
sudo systemctl enable --now direct.timer
systemctl list-timers | grep -E 'qtickets|vk_ads|direct'
```

## Настройка алертов

```bash
# Проверка healthcheck
curl -s http://127.0.0.1:8080/healthz

# Включение алертов
sudo systemctl enable --now alerts.timer
```

## Резервное копирование

```bash
# Создание полного бэкапа
sudo bash ops/backup_full.sh
```

## Доступы

- **ClickHouse HTTPS**: https://bi.zakaz-dashboard.ru
- **ClickHouse пользователь для DataLens**: datalens_reader / DataLens2024!Strong#Pass
- **Email для алертов**: ads-irsshow@yandex.ru