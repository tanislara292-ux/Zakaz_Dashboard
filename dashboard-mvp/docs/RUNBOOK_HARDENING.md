# RUNBOOK: Усиление безопасности ClickHouse

## Обзор

Этот документ описывает меры безопасности, примененные к ClickHouse в рамках EPIC-CH-07, и процедуры управления безопасностью.

## Реализованные меры безопасности

### 1. Сетевой периметр

#### Ограничение доступа по сети
- **Внешний доступ**: только через HTTPS-прокси Caddy
- **Локальный доступ**: только с localhost (127.0.0.1, ::1)
- **Закрытые порты**: 8123 (HTTP) и 9000 (Native) не экспортируются наружу

```xml
<!-- config.d/20-security.xml -->
<listen_host>127.0.0.1</listen_host>
<listen_host>::1</listen_host>
```

#### Docker Compose настройки
```yaml
# Порты не экспортируются наружу, доступ только через Caddy
# ports:
#   - "8123:8123"   # HTTP
#   - "9000:9000"   # Native
```

### 2. Ролевая модель доступа (RBAC)

#### Пользователи
1. **etl_writer** - для загрузки данных
2. **datalens_reader** - только чтение для BI
3. **backup_user** - для бэкапов и восстановления
4. **admin_min** - минимальные права администрирования

#### Роли
1. **role_etl_writer** - права на запись в стейджинг и витрины
2. **role_bi_reader** - права на чтение BI-представлений
3. **role_admin_min** - полные права на все базы данных

#### Профили производительности
1. **etl_profile** - для ETL процессов (10GB RAM, 4 потока)
2. **readonly_profile** - для чтения (2GB RAM, 2 потока)
3. **backup_profile** - для бэкапов (8GB RAM, 6 потоков)
4. **admin_profile** - для администрирования (16GB RAM, 8 потоков)

### 3. Аудит и логирование

#### Включенные логи
- **query_log** - все запросы к ClickHouse
- **query_thread_log** - логи потоков запросов
- **text_log** - текстовые сообщения
- **trace_log** - логи трассировки

#### Ретеншн логов
- Все логи хранятся 30 дней
- Автоматическое удаление по TTL

```xml
<meta.merge_tree>
    <ttl>system.query_log event_date + INTERVAL 30 DAY DELETE</ttl>
    <ttl>system.query_thread_log event_date + INTERVAL 30 DAY DELETE</ttl>
    <ttl>system.text_log event_date + INTERVAL 30 DAY DELETE</ttl>
    <ttl>system.trace_log event_date + INTERVAL 30 DAY DELETE</ttl>
</meta.merge_tree>
```

### 4. Управление паролями

#### Требования к паролям
- Минимальная длина: 12 символов
- Обязательные символы: верхний регистр, нижний регистр, цифры, специальные символы

```xml
<password_complexity>
    <min_length>12</min_length>
    <require_uppercase>1</require_uppercase>
    <require_lowercase>1</require_lowercase>
    <require_digits>1</require_digits>
    <require_special_characters>1</require_special_characters>
</password_complexity>
```

#### Хранение паролей
- Пароли хранятся в переменных окружения
- Используется SHA256 хеширование
- Регулярная ротация паролей

### 5. Ограничения ресурсов

#### Лимиты для пользователей
- **Максимальное время выполнения**: от 5 минут до 2 часов
- **Максимальная память**: от 2GB до 16GB
- **Максимальное количество потоков**: от 2 до 8

#### Квоты
- **ETL**: 1000 запросов в час, 10M строк результата
- **Backup**: 10 запросов за 2 часа
- **Default**: стандартные ограничения

### 6. Дополнительные меры безопасности

#### Отключение ненужных функций
- Внутренний DNS кэш отключен
- Удаленные серверы не настроены
- Минимальные права управления

#### Настройки сессий
- Время сессии по умолчанию: 1 час
- Максимальное время сессии: 24 часа
- Ограничение concurrent запросов

## Процедуры управления безопасностью

### 1. Ротация паролей

#### Ежемесячная ротация
```bash
# Генерация нового пароля
openssl rand -base64 32

# Обновление в .env
CLICKHOUSE_ETL_WRITER_PASSWORD=new_password
CLICKHOUSE_DATALENS_READER_PASSWORD=new_password
CLICKHOUSE_BACKUP_USER_PASSWORD=new_password
CLICKHOUSE_ADMIN_MIN_PASSWORD=new_password

# Перезапуск ClickHouse
docker-compose restart clickhouse
```

#### Проверка после ротации
```sql
-- Проверка подключения пользователей
SELECT user, address, failed FROM system.users WHERE user IN ('etl_writer', 'datalens_reader', 'backup_user', 'admin_min');
```

### 2. Аудит доступа

#### Проверка неудачных попыток входа
```sql
-- Последние неудачные попытки
SELECT * 
FROM system.query_log
WHERE event_date >= today() - 7
  AND exception LIKE '%Authentication%'
ORDER BY event_time DESC
LIMIT 10;
```

#### Анализ активности пользователей
```sql
-- Активность пользователей за последние 7 дней
SELECT 
    user,
    count() as query_count,
    sum(query_duration_ms) / 1000 as total_duration_sec,
    max(read_rows) as max_rows_read
FROM system.query_log
WHERE event_date >= today() - 7
  AND type = 'QueryFinish'
GROUP BY user
ORDER BY query_count DESC;
```

### 3. Мониторинг безопасности

#### Алерты безопасности
1. **Много неудачных попыток входа**
   - Порог: 5 неудачных попыток за 5 минут
   - Действие: уведомление в Telegram

2. **Подозрительные запросы**
   - Порог: DDL запросы от non-admin пользователей
   - Действие: уведомление в Telegram

3. **Высокая нагрузка**
   - Порог: использование памяти > 80%
   - Действие: уведомление в Telegram

#### Метрики для мониторинга
```sql
-- Использование памяти
SELECT 
    metric,
    value
FROM system.metrics
WHERE metric IN ('MemoryTracking', 'MaxMemoryUsage');

-- Активные соединения
SELECT count() 
FROM system.processes
WHERE elapsed > 60;
```

### 4. Управление доступом

#### Добавление нового пользователя
```sql
-- Создание пользователя
CREATE USER new_user IDENTIFIED BY 'strong_password';
GRANT role_bi_reader TO new_user;

-- Ограничение доступа по сети (если нужно)
ALTER USER new_user DEFAULT DATABASE bi;
```

#### Отзыв доступа
```sql
-- Отзыв прав
REVOKE ALL GRANTS FOR new_user;

-- Удаление пользователя
DROP USER IF EXISTS new_user;
```

### 5. Обновление конфигурации

#### Применение изменений
```bash
# Перезагрузка ClickHouse с новой конфигурацией
docker-compose restart clickhouse

# Проверка применения изменений
docker logs ch-zakaz | grep -i "error\|exception\|warning"
```

#### Валидация конфигурации
```bash
# Проверка синтаксиса XML
xmllint --noout config.xml

# Проверка настроек пользователей
clickhouse-client --query "SHOW USERS"
```

## Чек-лист безопасности

### Ежедневный
- [ ] Проверить логи на наличие ошибок
- [ ] Проверить метрики производительности
- [ ] Проверить активные соединения

### Еженедельный
- [ ] Проанализировать активность пользователей
- [ ] Проверка наличия подозрительных запросов
- [ ] Обновить whitelist IP-адресов (если используется)

### Ежемесячный
- [ ] Ротация паролей
- [ ] Обновление ClickHouse до последней версии
- [ ] Аудит прав доступа
- [ ] Проверка ретеншена логов

### Квартальный
- [ ] Полный аудит безопасности
- [ ] Тестирование процедур восстановления
- [ ] Обновление документации
- [ ] Проверка соответствия требованиям

## Восстановление после инцидента

### 1. Компрометация пароля
```bash
# Немедленная смена пароля
openssl rand -base64 32
# Обновить в .env и перезапустить ClickHouse
```

### 2. Несанкционированный доступ
```bash
# Блокировка IP-адреса
iptables -A INPUT -s malicious_ip -j DROP

# Отзыв доступа пользователя
clickhouse-client --query "DROP USER IF EXISTS compromised_user"
```

### 3. Утечка данных
```bash
# Анализ логов для определения масштаба
clickhouse-client --query "SELECT * FROM system.query_log WHERE query LIKE '%sensitive_table%'"

# Уведомление команды безопасности
```

## Контактная информация

- **Ответственный за безопасность**: security@example.com
- **DevOps команда**: devops@example.com
- **Экстренная связь**: +7-XXX-XXX-XX-XX

## Дополнительные ресурсы

- [ClickHouse Security Documentation](https://clickhouse.com/docs/en/operations/security/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Caddy Security Configuration](https://caddyserver.com/docs/caddyfile/directives/tls)