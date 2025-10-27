# Руководство по настройке реальных данных для интеграций

## Обзор

Документ содержит пошаговые инструкции по настройке всех токенов API и файлов конфигурации для работы с реальными данными из источников QTickets, VK Ads, Яндекс.Директ и Google Sheets.

## Предоставленные данные

### Обязательные данные

1. **Google Sheets**:
   - Email: chufarovk@gmail.com (Editor)
   - URL: https://docs.google.com/spreadsheets/d/1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc

2. **Yandex DataLens**:
   - Email: ads-irsshow@yandex.ru (Editor)
   - Email: irs20show24 (Editor)
   - ID: (требуется получить)

3. **Счетчики Метрики**:
   - Email: lazur.estate@yandex.ru (расшарен)

4. **Доступ к Яндекс.Директ**:
   - Email: ads-irsshow@yandex.ru
   - Email: irs20show24

5. **QTickets**:
   - API токен: 4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ

6. **VK Ads**:
   - API токен: (требуется получить)
   - ID рекламного кабинета: (требуется получить)
   - Email: lazur.estate@yandex.ru

7. **VPS**:
   - Хост: firstvds.ru
   - Пользователь: ads-irsshow@yandex.ru
   - Пароль: irs20show25

## Файлы конфигурации

### 1. QTickets (`secrets/.env.qtickets`)

```bash
# QTickets API Configuration

# API токен для доступа к QTickets API
QTICKETS_TOKEN=4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ

# Количество дней для загрузки исторических данных
QTICKETS_DAYS_BACK=30

# URL API QTickets
QTICKETS_API_URL=https://api.qtickets.ru/v1

# Таймаут запросов в секундах
QTICKETS_TIMEOUT=30

# Формат данных (csv, xlsx)
QTICKETS_FORMAT=csv

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/qtickets.log
```

### 2. VK Ads (`secrets/.env.vk`)

```bash
# VK Ads API Configuration

# API токен для доступа к VK Ads API
VK_TOKEN=your_vk_ads_api_token_here

# ID рекламных кабинетов (через запятую)
VK_ACCOUNT_IDS=123456789,987654321

# Количество дней для загрузки исторических данных
VK_DAYS_BACK=30

# URL API VK Ads
VK_API_URL=https://api.vk.com/method

# Версия API VK
VK_API_VERSION=5.131

# Таймаут запросов в секундах
VK_TIMEOUT=30

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/vk_ads.log
```

### 3. Яндекс.Директ (`secrets/.env.direct`)

```bash
# Yandex Direct API Configuration

# Логин аккаунта Яндекс.Директ
DIRECT_LOGIN=ads-irsshow@yandex.ru

# Токен для доступа к API Яндекс.Директ
DIRECT_TOKEN=your_yandex_direct_api_token_here

# ID клиента (если используется агентский аккаунт)
DIRECT_CLIENT_ID=your_client_id_here

# Количество дней для загрузки исторических данных
DIRECT_DAYS_BACK=30

# URL API Яндекс.Директ
DIRECT_API_URL=https://api.direct.yandex.ru/json/v5

# Таймаут запросов в секундах
DIRECT_TIMEOUT=30

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/direct.log
```

### 4. Google Sheets (`secrets/.env.sheets`)

```bash
# Google Sheets Configuration

# ID Google таблицы
GOOGLE_SHEETS_ID=1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc

# Email для доступа
GOOGLE_EMAIL=chufarovk@gmail.com

# Имя листа с данными
GOOGLE_SHEET_NAME=Лист1

# Диапазон данных
GOOGLE_RANGE=A:Z

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/sheets.log
```

### 5. VPS (`secrets/.env.vps`)

```bash
# VPS Configuration

# Хост VPS
VPS_HOST=firstvds.ru

# Пользователь VPS
VPS_USER=ads-irsshow@yandex.ru

# Пароль VPS
VPS_PASSWORD=irs20show25

# Порт SSH
VPS_SSH_PORT=22

# Часовой пояс
VPS_TIMEZONE=Europe/Moscow
```

## Инструкции по созданию файлов

### Шаг 1: Создание директории secrets

```bash
# Создание директории для секретов
mkdir -p dashboard-mvp/secrets
```

### Шаг 2: Создание файлов конфигурации

```bash
# Создание файла для QTickets
cat > dashboard-mvp/secrets/.env.qtickets << 'EOF'
# QTickets API Configuration

# API токен для доступа к QTickets API
QTICKETS_TOKEN=4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ

# Количество дней для загрузки исторических данных
QTICKETS_DAYS_BACK=30

# URL API QTickets
QTICKETS_API_URL=https://api.qtickets.ru/v1

# Таймаут запросов в секундах
QTICKETS_TIMEOUT=30

# Формат данных (csv, xlsx)
QTICKETS_FORMAT=csv

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/qtickets.log
EOF

# Создание файла для VK Ads
cat > dashboard-mvp/secrets/.env.vk << 'EOF'
# VK Ads API Configuration

# API токен для доступа к VK Ads API
VK_TOKEN=your_vk_ads_api_token_here

# ID рекламных кабинетов (через запятую)
VK_ACCOUNT_IDS=123456789,987654321

# Количество дней для загрузки исторических данных
VK_DAYS_BACK=30

# URL API VK Ads
VK_API_URL=https://api.vk.com/method

# Версия API VK
VK_API_VERSION=5.131

# Таймаут запросов в секундах
VK_TIMEOUT=30

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/vk_ads.log
EOF

# Создание файла для Яндекс.Директ
cat > dashboard-mvp/secrets/.env.direct << 'EOF'
# Yandex Direct API Configuration

# Логин аккаунта Яндекс.Директ
DIRECT_LOGIN=ads-irsshow@yandex.ru

# Токен для доступа к API Яндекс.Директ
DIRECT_TOKEN=your_yandex_direct_api_token_here

# Количество дней для загрузки исторических данных
DIRECT_DAYS_BACK=30

# URL API Яндекс.Директ
DIRECT_API_URL=https://api.direct.yandex.ru/json/v5

# Таймаут запросов в секундах
DIRECT_TIMEOUT=30

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/direct.log
EOF

# Создание файла для Google Sheets
cat > dashboard-mvp/secrets/.env.sheets << 'EOF'
# Google Sheets Configuration

# ID Google таблицы
GOOGLE_SHEETS_ID=1Ov6Fsb97KXyQx8UKOoy4JKLVpoLVUnn6faKH6C4gqVc

# Email для доступа
GOOGLE_EMAIL=chufarovk@gmail.com

# Имя листа с данными
GOOGLE_SHEET_NAME=Лист1

# Диапазон данных
GOOGLE_RANGE=A:Z

# Настройки логирования
LOG_LEVEL=INFO
LOG_JSON=false
LOG_FILE=logs/sheets.log
EOF

# Создание файла для VPS
cat > dashboard-mvp/secrets/.env.vps << 'EOF'
# VPS Configuration

# Хост VPS
VPS_HOST=firstvds.ru

# Пользователь VPS
VPS_USER=ads-irsshow@yandex.ru

# Пароль VPS
VPS_PASSWORD=irs20show25

# Порт SSH
VPS_SSH_PORT=22

# Часовой пояс
VPS_TIMEZONE=Europe/Moscow
EOF
```

### Шаг 3: Получение недостающих токенов

#### VK Ads токен

1. Перейдите в VK Ads: https://ads.vk.com/
2. Настройки → API → Создать токен
3. Выберите права: statistics, campaigns, ads
4. Скопируйте токен в файл `secrets/.env.vk`

#### ID рекламных кабинетов VK Ads

1. В VK Ads: Настройки → Рекламные кабинеты
2. Скопируйте ID кабинетов через запятую
3. Вставьте в `VK_ACCOUNT_IDS` в файле `secrets/.env.vk`

#### Яндекс.Директ токен

1. Перейдите в Яндекс.Директ: https://direct.yandex.ru/
2. Настройки → API → Создать токен
3. Выберите права: campaigns, reports, stats
4. Скопируйте логин и токен в файл `secrets/.env.direct`

## Шаблоны UTM-меток

### Формат UTM-меток

Все источники используют единый формат для `utm_content`:

```
{город}_{день}_{месяц}
```

Примеры:
- `tomsk_05_10`
- `moscow_12_11`
- `spb_15_09`

### Примеры UTM-тегов

#### Яндекс.Директ
```
utm_source=yandex&utm_medium=cpc&utm_campaign={campaign_id}&utm_content=tomsk_05_10
```

#### VK Ads
```
utm_source=vkontakte&utm_medium=cpc&utm_content=tomsk_05_10
```

#### Посев
```
utm_source=posev&utm_medium=dd.mm&utm_campaign=gruppa_posev&utm_content=tomsk_05_10
```

#### Директ-контакты
```
utm_source=dk&utm_content=tomsk_05_10
```

## Запуск интеграций с реальными данными

### 1. QTickets

```bash
# Запуск загрузчика QTickets
cd dashboard-mvp
python3 integrations/qtickets/loader.py --env secrets/.env.qtickets --days 7

# Проверка результатов
docker exec ch-zakaz clickhouse-client --database=zakaz --query "SELECT count() FROM stg_qtickets_sales_raw"
```

### 2. Google Sheets

```bash
# Запуск загрузчика Google Sheets
cd dashboard-mvp
python3 archive/sheets/init.py
python3 archive/sheets/validate.py

# Проверка результатов
docker exec ch-zakaz clickhouse-client --database=zakaz --query "SELECT count() FROM stg_google_sheets_raw"
```

### 3. VK Ads

```bash
# Запуск загрузчика VK Ads
cd dashboard-mvp
python3 integrations/vk_ads/loader.py --env secrets/.env.vk --days 7

# Проверка результатов
docker exec ch-zakaz clickhouse-client --database=zakaz --query "SELECT count() FROM fact_vk_ads_daily"
```

### 4. Яндекс.Директ

```bash
# Запуск загрузчика Яндекс.Директ
cd dashboard-mvp
python3 integrations/direct/loader.py --env secrets/.env.direct --days 7

# Проверка результатов
docker exec ch-zakaz clickhouse-client --database=zakaz --query "SELECT count() FROM fact_direct_daily"
```

## Проверка данных в ClickHouse

### Проверка свежести данных

```sql
-- Проверка свежести данных по всем источникам
SELECT 
    'qtickets' as source,
    max(event_date) as latest_date,
    today() - max(event_date) as days_behind
FROM zakaz.stg_qtickets_sales_raw

UNION ALL

SELECT 
    'sheets' as source,
    max(event_date) as latest_date,
    today() - max(event_date) as days_behind
FROM zakaz.stg_google_sheets_raw

UNION ALL

SELECT 
    'vk_ads' as source,
    max(stat_date) as latest_date,
    today() - max(stat_date) as days_behind
FROM zakaz.fact_vk_ads_daily

UNION ALL

SELECT 
    'direct' as source,
    max(stat_date) as latest_date,
    today() - max(stat_date) as days_behind
FROM zakaz.fact_direct_daily
ORDER BY source;
```

### Проверка качества данных

```sql
-- Проверка на дубликаты в данных продаж
SELECT 
    source,
    count() - countDistinct(src_msg_id) as duplicates
FROM (
    SELECT 'qtickets' as source, src_msg_id FROM zakaz.stg_qtickets_sales_raw
    UNION ALL
    SELECT 'sheets' as source, src_msg_id FROM zakaz.stg_google_sheets_raw
)
GROUP BY source;
```

## Настройка автоматической загрузки

### Systemd таймеры

```bash
# Настройка таймеров
cd dashboard-mvp
bash ops/setup_timers.sh

# Запуск таймеров
sudo systemctl enable etl@qtickets.timer
sudo systemctl enable etl@google_sheets.timer
sudo systemctl enable etl@vk_ads.timer
sudo systemctl enable etl@direct.timer

sudo systemctl start etl@qtickets.timer
sudo systemctl start etl@google_sheets.timer
sudo systemctl start etl@vk_ads.timer
sudo systemctl start etl@direct.timer

# Проверка статуса
systemctl list-timers | grep -E 'qtickets|sheets|vk_ads|direct'
```

## Метрики продаж

Метрики продаж учитываются как выручка минус возвраты (сумма всех источников).

### Агрегированные данные

```sql
-- Агрегированные данные по продажам из всех источников
SELECT
    d,
    city,
    SUM(tickets_sold) as tickets_total,
    SUM(revenue - refunds_amount) as revenue_total
FROM (
    SELECT event_date as d, city, tickets_sold, revenue, refunds_amount FROM zakaz.stg_qtickets_sales_raw
    UNION ALL
    SELECT event_date as d, city, tickets_sold, revenue, refunds_amount FROM zakaz.stg_google_sheets_raw
)
WHERE event_date >= today() - 30
GROUP BY d, city
ORDER BY d DESC, revenue_total DESC;
```

## Проблемы и решения

### Проблема: Токены не работают

**Решение:**
1. Проверьте срок действия токенов
2. Убедитесь, что у токены есть необходимые права доступа
3. Проверьте правильность формата в файлах .env

### Проблема: Google Sheets недоступен

**Решение:**
1. Убедитесь, что предоставлен доступ Editor
2. Проверьте, что сервисный аккаунт создан для доступа к Drive API
3. Проверьте ID таблицы в файле .env

### Проблема: VK Ads API возвращает ошибку

**Решение:**
1. Проверьте, что токен имеет права statistics, campaigns, ads
2. Убедитесь, что ID кабинетов правильные
3. Проверьте лимиты API VK Ads

### Проблема: Яндекс.Директ API возвращает ошибку

**Решение:**
1. Проверьте, что токен имеет права campaigns, reports, stats
2. Убедитесь, что логин и токен правильные
3. Проверьте лимиты API Яндекс.Директ

## Метаданные и логирование

### Просмотр истории запусков

```sql
-- Просмотр последних запусков
SELECT 
    job,
    started_at,
    finished_at,
    status,
    rows_processed,
    message
FROM zakaz.meta_job_runs
ORDER BY started_at DESC
LIMIT 10;
```

### Логи интеграций

```bash
# Просмотр логов QTickets
tail -f logs/qtickets.log

# Просмотр логов VK Ads
tail -f logs/vk_ads.log

# Просмотр логов Яндекс.Директ
tail -f logs/direct.log

# Просмотр логов Google Sheets
tail -f logs/sheets.log
```

---

**Статус**: 🟡 Документация готова, требуется создание файлов конфигурации
**Дата**: 20.10.2025
**Версия**: 1.0.0