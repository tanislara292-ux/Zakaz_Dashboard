# ПОЛНЫЙ ПАКЕТ РАЗВЕРТЫВАНИЯ ZAKAZ DASHBOARD ДЛЯ ЗАКАЗЧИКА

## Обзор

Документ представляет полный пакет инструкций для развертывания системы Zakaz Dashboard на сервере заказчика. Включает все необходимые шаги, проверки и руководство по решению проблем.

---

## СОДЕРЖАНИЕ ПАКЕТА

### 📋 Основные документы

1. **[021_UBUNTU_DEPLOYMENT_GUIDE.md](021_UBUNTU_DEPLOYMENT_GUIDE.md)** - Полное руководство по развертыванию на Ubuntu
2. **[022_MIGRATION_GUIDE.md](022_MIGRATION_GUIDE.md)** - Инструкция по миграции со старого кода
3. **[023_DATALENS_SETUP_GUIDE.md](023_DATALENS_SETUP_GUIDE.md)** - Подключение и настройка Yandex DataLens
4. **[024_COMPREHENSIVE_TROUBLESHOOTING_GUIDE.md](024_COMPREHENSIVE_TROUBLESHOOTING_GUIDE.md)** - Комплексное руководство по решению проблем

### 📊 Дополнительные материалы

5. **[019_FINAL_VERIFICATION_REPORT.md](019_FINAL_VERIFICATION_REPORT.md)** - Отчет о верификации системы
6. **[020_QTICKETS_PRODUCTION_TESTING.md](020_QTICKETS_PRODUCTION_TESTING.md)** - Тестирование QTickets API
7. **[019_PRODUCTION_TESTING_PLAN.md](019_PRODUCTION_TESTING_PLAN.md)** - План тестирования

---

## 🚀 БЫСТРЫЙ СТАРТ ДЛЯ ЗАКАЗЧИКА

### Шаг 1: Подготовка сервера (15 минут)

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Клонирование репозитория
sudo mkdir -p /opt/zakaz_dashboard
sudo chown $USER:$USER /opt/zakaz_dashboard
cd /opt/zakaz_dashboard
git clone https://github.com/tanislara292-ux/Zakaz_Dashboard.git .
git checkout main
```

### Шаг 2: Настройка ClickHouse (10 минут)

```bash
# Переход в директорию ClickHouse
cd dashboard-mvp/infra/clickhouse

# Настройка конфигурации
cp .env.example .env
nano .env  # Изменить пароль администратора

# Запуск ClickHouse
docker-compose up -d

# Инициализация схемы
cd ../..
bash scripts/bootstrap_clickhouse.sh
```

### Шаг 3: Настройка токенов (5 минут)

```bash
# Создание файлов секретов
mkdir -p secrets

# Настройка QTickets API
nano secrets/.env.qtickets_api
# Вставить токен и настройки

# Настройка VK Ads
nano secrets/.env.vk
# Вставить токен VK

# Настройка Яндекс.Директ
nano secrets/.env.direct
# Вставить токен Яндекса
```

### Шаг 4: Сборка и запуск сервисов (10 минут)

```bash
# Сборка образа
docker build -f dashboard-mvp/integrations/qtickets_api/Dockerfile -t qtickets_api:latest .

# Настройка systemd юнитов
sudo cp dashboard-mvp/ops/systemd/*.service /etc/systemd/system/
sudo cp dashboard-mvp/ops/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Запуск таймеров
sudo systemctl enable --now qtickets_api.timer
sudo systemctl enable --now vk_ads.timer
sudo systemctl enable --now direct.timer
```

### Шаг 5: Настройка HTTPS (5 минут)

```bash
# Установка Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy -y

# Настройка Caddyfile
sudo nano /etc/caddy/Caddyfile
# Вставить конфигурацию для bi.zakaz-dashboard.ru

# Запуск Caddy
sudo systemctl enable --now caddy
```

### Шаг 6: Подключение DataLens (10 минут)

1. Открыть https://datalens.yandex.ru/
2. Создать подключение к ClickHouse:
   - Хост: `bi.zakaz-dashboard.ru`
   - Порт: `443`
   - База: `zakaz`
   - Пользователь: `datalens_reader`
   - Пароль: `ChangeMe123!`
3. Создать источники данных и дашборды

---

## 📋 ПОЛНЫЙ ЧЕК-ЛИСТ РАЗВЕРТЫВАНИЯ

### ✅ Предварительные требования

- [ ] **Сервер**: Ubuntu 20.04+ с 4+ CPU, 8GB+ RAM, 100GB+ SSD
- [ ] **Сеть**: Открыты порты 80, 443, настроен домен
- [ ] **Доступ**: SSH с правами sudo
- [ ] **Токены**: Получены API токены QTickets, VK Ads, Яндекс.Директ

### ✅ Инфраструктура

- [ ] **Docker**: Установлен и работает
- [ ] **Docker Compose**: Установлен
- [ ] **Git**: Клонирован репозиторий
- [ ] **Права**: Настроены права доступа к директориям

### ✅ ClickHouse

- [ ] **Конфигурация**: `.env` файл настроен
- [ ] **Контейнер**: Запущен и здоров
- [ ] **Схема**: Применена через `bootstrap_clickhouse.sh`
- [ ] **Пользователи**: Созданы admin, etl_writer, datalens_reader
- [ ] **Таблицы**: Созданы все необходимые таблицы

### ✅ Секреты и токены

- [ ] **QTickets API**: `.env.qtickets_api` настроен
- [ ] **VK Ads**: `.env.vk` настроен
- [ ] **Яндекс.Директ**: `.env.direct` настроен
- [ ] **Права**: Файлы секретов имеют права 600

### ✅ Сервисы

- [ ] **Docker образ**: qtickets_api собран
- [ ] **Тестовый запуск**: Dry-run работает корректно
- [ ] **Systemd юниты**: Скопированы и перезагружены
- [ ] **Таймеры**: Включены и работают по расписанию

### ✅ HTTPS и доступность

- [ ] **Caddy**: Установлен и настроен
- [ ] **SSL сертификат**: Настроен для домена
- [ ] **HTTPS доступ**: ClickHouse доступен по HTTPS
- [ ] **Проверка**: `curl -k https://bi.zakaz-dashboard.ru/?query=SELECT%201` работает

### ✅ DataLens

- [ ] **Подключение**: Создано и проверено
- [ ] **Источники**: Созданы все необходимые источники
- [ ] **Датасеты**: Настроены с правильными типами
- [ ] **Дашборды**: Созданы и отображают данные
- [ ] **Автообновление**: Настроено с интервалом 15 минут

### ✅ Мониторинг

- [ ] **Алерты**: Настроены email уведомления
- [ ] **Логирование**: Настроено ротация логов
- [ ] **Бэкапы**: Настроены автоматические бэкапы
- [ ] **Проверки**: Настроены ежедневные проверки

---

## 🔧 КОНФИГУРАЦИОННЫЕ ФАЙЛЫ

### Основные параметры для настройки

#### ClickHouse (.env)
```bash
CLICKHOUSE_ADMIN_USER=admin
CLICKHOUSE_ADMIN_PASSWORD=СМЕНИТЕ_ЭТОТ_ПАРОЛЬ
CLICKHOUSE_DB=zakaz
CLICKHOUSE_TZ=Europe/Moscow
```

#### QTickets API (.env.qtickets_api)
```bash
QTICKETS_BASE_URL=https://qtickets.ru/api/rest/v1
QTICKETS_TOKEN=ВАШ_БОЕВОЙ_ТОКЕН
CLICKHOUSE_HOST=localhost
CLICKHOUSE_USER=etl_writer
CLICKHOUSE_PASSWORD=EtL2024!Strong#Pass
DRY_RUN=false
```

#### VK Ads (.env.vk)
```bash
VK_ACCESS_TOKEN=ВАШ_VK_ТОКЕН
VK_ACCOUNT_ID=ВАШ_ACCOUNT_ID
CLICKHOUSE_HOST=localhost
CLICKHOUSE_USER=etl_writer
```

#### Яндекс.Директ (.env.direct)
```bash
DIRECT_CLIENT_ID=ВАШ_CLIENT_ID
DIRECT_CLIENT_SECRET=ВАШ_CLIENT_SECRET
DIRECT_TOKEN=ВАШ_ЯНДЕКС_ТОКЕН
CLICKHOUSE_HOST=localhost
```

---

## 🚨 КРИТИЧЕСКИЕ ШАГИ БЕЗОПАСНОСТИ

### 1. Изменение паролей по умолчанию

```bash
# Изменить пароль администратора ClickHouse
docker exec ch-zakaz clickhouse-client --user=admin --password='admin_pass' -q "
ALTER USER admin IDENTIFIED BY 'НОВЫЙ_СИЛЬНЫЙ_ПАРОЛЬ'"

# Изменить пароль DataLens пользователя
docker exec ch-zakaz clickhouse-client --user=admin --password='НОВЫЙ_ПАРОЛЬ' -q "
ALTER USER datalens_reader IDENTIFIED BY 'НОВЫЙ_ПАРОЛЬ_DATALENS'"
```

### 2. Настройка файрвола

```bash
# Базовая настройка UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Защита секретов

```bash
# Установка правильных прав
chmod 600 /opt/zakaz_dashboard/secrets/.env*
chown $USER:$USER /opt/zakaz_dashboard/secrets/.env*

# Добавление в .gitignore
echo "secrets/" >> .gitignore
echo "*.env" >> .gitignore
```

---

## 📊 ПРОВЕРКА РАБОТОСПОСОБНОСТИ

### Быстрая проверка (5 минут)

```bash
# Запуск системной проверки
cd /opt/zakaz_dashboard
bash dashboard-mvp/ops/system_check.sh

# Проверка загрузки данных
docker exec ch-zakaz clickhouse-client --user=datalens_reader --password='ChangeMe123!' -q "
SELECT 
    'Data Check' as metric,
    count() as rows,
    max(sale_ts) as latest
FROM zakaz.stg_qtickets_api_orders_raw 
WHERE sale_ts >= today() - INTERVAL 1 DAY"
```

### Полная проверка (30 минут)

1. **Проверить все таймеры**: `systemctl list-timers`
2. **Проверить логи сервисов**: `journalctl -u qtickets_api.service -n 20`
3. **Проверить данные в ClickHouse**: Через DataLens или CLI
4. **Проверить HTTPS доступ**: Через браузер или curl
5. **Проверить алерты**: Проверить email и таблицу алертов

---

## 🆘 ПОДДЕРЖКА И КОНТАКТЫ

### Уровни поддержки

| Проблема | Контакты | Время реакции |
|-----------|-----------|--------------|
| **Инструкции и документация** | Данные руководства | Самостоятельно |
| **Технические проблемы** | Техническая поддержка: [контакт] | 4 часа |
| **Критические сбои** | Экстренный контакт: [контакт] | 30 минут |

### Полезные команды

```bash
# Статус системы
bash dashboard-mvp/ops/system_check.sh

# Перезапуск сервисов
sudo systemctl restart qtickets_api.service

# Просмотр логов
journalctl -u qtickets_api.service -f

# Проверка таймеров
systemctl list-timers

# Мониторинг ресурсов
docker stats
htop
df -h
```

---

## 📚 ПОЛЕЗНЫЕ РЕСУРСЫ

### Документация

- **Основное руководство**: [021_UBUNTU_DEPLOYMENT_GUIDE.md](021_UBUNTU_DEPLOYMENT_GUIDE.md)
- **Миграция**: [022_MIGRATION_GUIDE.md](022_MIGRATION_GUIDE.md)
- **DataLens**: [023_DATALENS_SETUP_GUIDE.md](023_DATALENS_SETUP_GUIDE.md)
- **Troubleshooting**: [024_COMPREHENSIVE_TROUBLESHOOTING_GUIDE.md](024_COMPREHENSIVE_TROUBLESHOOTING_GUIDE.md)

### SQL-запросы для DataLens

```sql
-- Основные продажи
SELECT 
    event_date,
    city,
    event_name,
    tickets_sold,
    revenue,
    (revenue - refunds_amount) AS net_revenue
FROM zakaz.v_qtickets_sales_latest
WHERE event_date >= today() - INTERVAL 30 DAY

-- Маркетинговые данные
SELECT 
    d AS event_date,
    city,
    spend_total,
    net_revenue,
    romi
FROM zakaz.v_marketing_daily
WHERE d >= today() - INTERVAL 30 DAY

-- Свежесть данных
SELECT 
    source,
    table_name,
    latest_date,
    days_behind
FROM zakaz.v_qtickets_freshness
```

---

## ✅ ЗАВЕРШЕНИЕ РАЗВЕРТЫВАНИЯ

После выполнения всех шагов:

1. ✅ **Система развернута** и полностью функциональна
2. ✅ **Данные загружаются** из всех источников
3. ✅ **DataLens подключен** и дашборды работают
4. ✅ **Мониторинг настроен** и алерты работают
5. ✅ **Безопасность обеспечена** на базовом уровне

### Передача заказчику

1. **Предоставьте доступы**:
   - URL дашбордов DataLens
   - Учетные данные для доступа
   - Контакты поддержки

2. **Проведите обучение**:
   - Работа с дашбордами
   - Использование фильтров
   - Чтение отчетов

3. **Передайте документацию**:
   - Данный пакет инструкций
   - Контакты поддержки
   - Рекомендации по эксплуатации

---

## 📈 СЛЕДУЮЩИЕ ШАГИ РАЗВИТИЯ

### Краткосрочные (1-3 месяца)

- Настройка дополнительных алертов
- Оптимизация производительности запросов
- Расширение дашбордов новыми метриками
- Настройка резервного копирования в облако

### Среднесрочные (3-6 месяцев)

- Интеграция дополнительных источников данных
- Создание прогнозных моделей
- Настройка системы мониторинга (Prometheus/Grafana)
- Автоматизация обновлений

### Долгосрочные (6+ месяцев)

- Масштабирование на кластер ClickHouse
- Внедрение ML-моделей для аналитики
- Создание мобильного приложения
- Интеграция с CRM-системами

---

**Версия пакета**: 1.0.0  
**Дата создания**: $(date +%Y-%m-%d)  
**Последнее обновление**: $(date +%Y-%m-%d)

---

*Этот пакет предоставляет все необходимые инструкции для успешного развертывания и эксплуатации системы Zakaz Dashboard. При возникновении вопросов обращайтесь к подробным руководствам или в службу поддержки.*