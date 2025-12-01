# Handover Package - Zakaz Dashboard

## Обзор проекта

Проект "Zakaz Dashboard" - это система аналитики для отслеживания продаж и эффективности рекламных кампаний. Система собирает данные из QTickets, VK Ads и Яндекс.Директ, хранит их в ClickHouse и визуализирует в Yandex DataLens.

## Инфраструктура

### Сервер
- **VPS**: FirstVDS
- **Доступ**: ads-irsshow@yandex.ru / irs20show25
- **Домен**: bi.zakaz-dashboard.ru

### Компоненты
- **ClickHouse**: СУБД для хранения данных
- **Caddy**: Реверс-прокси для HTTPS
- **Systemd таймеры**: Оркестрация загрузки данных
- **DataLens**: Визуализация данных

## Доступы

### ClickHouse
- **HTTPS**: https://bi.zakaz-dashboard.ru
- **Пользователь для DataLens**: datalens_reader
- **Пароль**: DataLens2024!Strong#Pass

### Источники данных
- **QTickets API**: токен в secrets/.env.qtickets
- **VK Ads**: lazur.estate@yandex.ru, токен в secrets/.env.vk_ads
- **Яндекс.Директ**: ads-irsshow@yandex.ru / irs20show24, токен в secrets/.env.direct

### DataLens
- **Дашборд**: [ссылка на дашборд]
- **Доступ**: RomaVXION@yandex.ru, ads-irsshow@yandex.ru

## Ключевые файлы

### Конфигурация
- `secrets/.env.*` - секреты (права 600)
- `infra/clickhouse/docker-compose.yml` - конфигурация ClickHouse
- `infra/clickhouse/users.d/10-users.xml` - пользователи ClickHouse

### Скрипты
- `ops/deploy_infrastructure.sh` - развертывание инфраструктуры
- `ops/backfill_data.sh` - загрузка исторических данных
- `ops/setup_timers.sh` - настройка таймеров
- `ops/system_check.sh` - проверка системы

### Документация
- `docs/RUNBOOK_*.md` - руководства по эксплуатации
- `ops/VPS_DEPLOYMENT_INSTRUCTIONS.md` - инструкция по развертыванию
- `ops/TOKEN_GUIDE.md` - инструкция по получению токенов
- `ops/DATALENS_SETUP.md` - инструкция по настройке DataLens

## Расписание загрузки данных

| Источник | Расписание | Таймер |
|----------|------------|--------|
| QTickets | Каждые 30 минут | qtickets.timer |
| VK Ads | Ежедневно 00:00 МСК | vk_ads.timer |
| Яндекс.Директ | Ежедневно 00:10 МСК | direct.timer |
| Алерты | Каждые 2 часа | alerts.timer |
| Smoke-тесты | Ежедневно 06:00 МСК | smoke_test_integrations.timer |

## Мониторинг

### Healthcheck
- **URL**: http://localhost:8080/healthz
- **Детальный**: http://localhost:8080/healthz/detailed
- **Свежесть данных**: http://localhost:8080/healthz/freshness

### Алерты
- **Email**: ads-irsshow@yandex.ru
- **SMTP**: smtp.yandex.ru:465

### Логи
```bash
# Просмотр логов таймеров
journalctl -u qtickets.service -f
journalctl -u vk_ads.service -f
journalctl -u direct.service -f
journalctl -u alerts.service -f

# Проверка статуса таймеров
systemctl list-timers | grep -E 'qtickets|vk_ads|direct|alerts'
```

## Резервное копирование

### Типы бэкапов
- **Полные**: ежедневно в 02:30 МСК
- **Инкрементальные**: каждые 4 часа

### Управление
```bash
# Создание полного бэкапа
sudo bash ops/backup_full.sh

# Проверка статуса бэкапов
docker exec ch-zakaz clickhouse-client --user=datalens_reader --password=DataLens2024!Strong#Pass -q "
SELECT backup_name, status, ts FROM meta.backup_runs ORDER BY ts DESC LIMIT 10"
```

## Обслуживание

### Ежедневные задачи
1. Проверка статуса таймеров
2. Проверка алертов
3. Проверка свежести данных

### Еженедельные задачи
1. Проверка логов на ошибки
2. Проверка свободного места на диске
3. Тестирование восстановления из бэкапа

### Ежемесячные задачи
1. Обновление токенов API
2. Проверка производительности системы
3. Обновление документации

## Устранение проблем

### Отсутствие данных
1. Проверьте статус таймеров: `systemctl list-timers`
2. Проверьте логи: `journalctl -u qtickets.service -n 50`
3. Проверьте токены в secrets/
4. Запустите загрузку вручную: `bash ops/backfill_data.sh`

### Проблемы с доступом
1. Проверьте работу ClickHouse: `docker exec ch-zakaz clickhouse-client -q "SELECT 1"`
2. Проверьте HTTPS: `curl -I https://bi.zakaz-dashboard.ru/ping`
3. Проверьте healthcheck: `curl http://localhost:8080/healthz`

### Алерты не приходят
1. Проверьте настройки SMTP в secrets/.env.alerts
2. Проверьте логи алертов: `journalctl -u alerts.service -n 50`
3. Проверьте работу SMTP: `telnet smtp.yandex.ru 465`

## Контакты

- **Разработчик**: [контакт разработчика]
- **Поддержка ClickHouse**: [документация ClickHouse]
- **Поддержка DataLens**: [документация DataLens]

## Следующие шаги

1. **Настроить мониторинг**: Prometheus/Grafana для детального мониторинга
2. **Оптимизировать запросы**: Материализованные представления в ClickHouse
3. **Расширить аналитику**: Дополнительные дашборды и метрики
4. **Автоматизировать обновление**: CI/CD для развертывания изменений

## Приложение

### Схема данных
- `zakaz.stg_qtickets_sales` - сырые данные о продажах
- `zakaz.stg_vk_ads_daily` - статистика VK Ads
- `zakaz.fact_direct_daily` - статистика Яндекс.Директ
- `zakaz.v_sales_latest` - актуальные продажи
- `zakaz.v_marketing_daily` - маркетинговая статистика
- `zakaz.meta_job_runs` - метаданные о запусках
- `zakaz.alerts` - алерты
- `meta.backup_runs` - информация о бэкапах

### SQL-запросы для проверки
```sql
-- Проверка свежести данных
SELECT max(event_date) FROM zakaz.v_sales_latest;
SELECT max(d) FROM zakaz.v_marketing_daily;

-- Проверка объемов данных
SELECT count() FROM zakaz.v_sales_latest WHERE event_date >= today()-7;
SELECT sum(spend_total) FROM zakaz.v_marketing_daily WHERE d >= today()-7;

-- Проверка ошибок
SELECT * FROM zakaz.alerts ORDER BY created_at DESC LIMIT 10;
SELECT * FROM zakaz.meta_job_runs WHERE status = 'error' ORDER BY started_at DESC LIMIT 10;
```

---
**Дата создания**: $(date +%Y-%m-%d)
**Версия**: 1.0.0