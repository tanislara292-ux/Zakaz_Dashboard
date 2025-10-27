# Текущий статус и инструкции по развертыванию для тестирования

## Текущий статус системы

### Что проверено

✅ **Документация подготовлена**
- Создан полный план подключения к DataLens
- Подготовлены технические спецификации
- Созданы руководства для заказчика

❌ **Инфраструктура не развернута**
- Docker контейнеры не запущены
- ClickHouse недоступен
- Домен bi.zakaz-dashboard.ru не отвечает

### Результаты проверки

```
=== Проверка доступности ClickHouse для DataLens ===
Дата: Mon Oct 20 12:51:30 MSK 2025

Параметры подключения:
  Хост: bi.zakaz-dashboard.ru
  Порт: 443
  База данных: zakaz
  Пользователь: datalens_reader

1. Проверка доступности хоста...
❌ Хост bi.zakaz-dashboard.ru недоступен

2. Проверка HTTPS доступности...
❌ HTTPS доступ к ClickHouse не работает

❌ Система не готова к настройке DataLens
```

## Что нужно сделать для развертывания

### Вариант 1: Развертывание на локальной машине (для тестирования)

#### Предварительные требования

1. **Docker Desktop** установлен и запущен
2. **Git** для клонирования репозитория
3. **Базовые знания** командной строки

#### Шаги развертывания

1. **Перейти в директорию проекта**
   ```bash
   cd dashboard-mvp/infra/clickhouse
   ```

2. **Проверить наличие .env файла**
   ```bash
   ls -la ../../.env
   ```

3. **Запустить Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Проверить статус контейнеров**
   ```bash
   docker ps
   ```

5. **Проверить доступность ClickHouse**
   ```bash
   curl http://localhost:8080/?query=SELECT%201
   ```

6. **Проверить доступность по HTTPS**
   ```bash
   curl -k https://localhost:8443/?query=SELECT%201
   ```

#### Изменения для локального тестирования

Для локального тестирования нужно изменить Caddyfile:

```caddyfile
# Локальная конфигурация без SSL
localhost:8080 {
    reverse_proxy clickhouse:8123 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
}

# HTTPS для локального тестирования (опционально)
localhost:8443 {
    tls internal
    reverse_proxy clickhouse:8123 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

### Вариант 2: Развертывание на сервере (боевой вариант)

#### Предварительные требования

1. **Сервер** с Ubuntu/CentOS
2. **Docker и Docker Compose** установлены
3. **Домен** bi.zakaz-dashboard.ru настроен и指向 сервер
4. **Порты** 80 и 443 открыты

#### Шаги развертывания

1. **Подключиться к серверу**
   ```bash
   ssh user@server_ip
   ```

2. **Клонировать репозиторий**
   ```bash
   git clone <repository_url>
   cd Zakaz_Dashboard/dashboard-mvp
   ```

3. **Настроить .env файл**
   ```bash
   cp .env.sample .env
   # Отредактировать .env с реальными паролями
   ```

4. **Развернуть инфраструктуру**
   ```bash
   bash ops/full_deployment.sh
   ```

5. **Проверить работу системы**
   ```bash
   bash ops/system_check.sh
   ```

## Параметры для DataLens

### Для локального тестирования

- **Хост**: localhost
- **Порт**: 8080 (HTTP) или 8443 (HTTPS)
- **База данных**: zakaz
- **Имя пользователя**: datalens_reader
- **Пароль**: DataLens2024!Strong#Pass
- **Использовать HTTPS**: Нет (для порта 8080) или Да (для порта 8443)

### Для боевого сервера

- **Хост**: bi.zakaz-dashboard.ru
- **Порт**: 443
- **База данных**: zakaz
- **Имя пользователя**: datalens_reader
- **Пароль**: DataLens2024!Strong#Pass
- **Использовать HTTPS**: Да

## SQL-запросы для проверки данных

После развертывания системы проверьте наличие данных:

```sql
-- Проверка таблиц
SHOW TABLES FROM zakaz;

-- Проверка данных продаж
SELECT 
    count() as total_rows,
    min(event_date) as min_date,
    max(event_date) as max_date
FROM zakaz.v_sales_latest;

-- Проверка маркетинговых данных
SELECT 
    count() as total_rows,
    min(d) as min_date,
    max(d) as max_date
FROM zakaz.v_marketing_daily;

-- Проверка свежести данных
SELECT 
    'sales' as source,
    max(event_date) as latest_date,
    today() - max(event_date) as days_behind
FROM zakaz.v_sales_latest

UNION ALL

SELECT 
    'marketing' as source,
    max(d) as latest_date,
    today() - max(d) as days_behind
FROM zakaz.v_marketing_daily;
```

## Создание источников данных в DataLens

### Источник продаж

```sql
SELECT
    event_date,
    city,
    event_name,
    tickets_sold,
    revenue,
    refunds_amount,
    (revenue - refunds_amount) AS net_revenue
FROM zakaz.v_sales_latest
```

### Источник маркетинга

```sql
SELECT
    d,
    city,
    spend_total,
    net_revenue,
    romi
FROM zakaz.v_marketing_daily
```

## Рекомендации

### Для быстрого тестирования

1. Используйте локальный вариант развертывания
2. Загрузите тестовые данные в ClickHouse
3. Создайте простые дашборды в DataLens
4. Проверьте все функции перед развертыванием на сервере

### Для боевого развертывания

1. Используйте скрипт `ops/full_deployment.sh`
2. Настройте SSL-сертификат для домена
3. Настройте мониторинг и алерты
4. Проведите полное тестирование перед передачей заказчику

## Следующие шаги

1. **Выберите вариант развертывания** (локальный или серверный)
2. **Выполните развертывание** согласно инструкциям
3. **Проверьте работу системы** с помощью скриптов проверки
4. **Настройте DataLens** с созданными источниками данных
5. **Создайте дашборды** согласно спецификациям
6. **Проведите тестирование** всех функций
7. **Подготовьте систему** к передаче заказчику

---

**Статус**: ⚠️ Система не развернута, требуется развертывание
**Дата проверки**: 20.10.2025
**Следующее действие**: Развертывание инфраструктуры