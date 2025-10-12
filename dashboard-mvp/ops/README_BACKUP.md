# Настройка резервного копирования ClickHouse

## Обзор

Этот документ описывает настройку системы резервного копирования ClickHouse, реализованной в рамках EPIC-CH-07.

## Предварительные требования

1. ClickHouse запущен и доступен
2. Настроены пользователи ClickHouse (см. `infra/clickhouse/users.d/10-users.xml`)
3. Установлены необходимые утилиты (для S3 режима: aws-cli)

## Настройка

### 1. Переменные окружения

Добавьте в `.env` файл следующие переменные:

```bash
# Режим бэкапа: s3 или local
BACKUP_MODE=s3

# Директория для локальных бэкапов (только для local режима)
BACKUP_DIR=/opt/clickhouse/backups

# Политика хранения
FULL_RETENTION_DAYS=28      # Полные бэкапы: 4 недели
INCR_RETENTION_DAYS=7       # Инкрементальные: 7 дней
GOLDEN_RETENTION_MONTHS=12  # Золотые бэкапы: 1 год

# Пароль пользователя backup_user
CLICKHOUSE_BACKUP_USER_PASSWORD=strong_password_here

# S3 конфигурация (только для s3 режима)
S3_BUCKET=your-backup-bucket
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
```

### 2. Настройка пользователей ClickHouse

Убедитесь, что пользователь `backup_user` существует и имеет необходимые права:

```sql
-- Проверка пользователя
SELECT * FROM system.users WHERE name = 'backup_user';

-- Создание пользователя (если отсутствует)
CREATE USER backup_user IDENTIFIED BY 'strong_password_here';
GRANT INSERT, SELECT ON meta.backup_runs TO backup_user;
GRANT SELECT ON zakaz.* TO backup_user;
GRANT SELECT ON bi.* TO backup_user;
GRANT SELECT ON meta.* TO backup_user;
```

### 3. Настройка S3 (опционально)

Если используется S3 режим, настройте aws-cli:

```bash
# Установка aws-cli
pip install awscli

# Конфигурация
aws configure
AWS Access Key ID: your_access_key
AWS Secret Access Key: your_secret_key
Default region name: us-east-1
Default output format: json
```

### 4. Настройка systemd таймеров

Скопируйте файлы таймеров в систему:

```bash
# Копирование сервисов
sudo cp infra/systemd/backup@.service /etc/systemd/system/
sudo cp infra/systemd/backup@full.timer /etc/systemd/system/
sudo cp infra/systemd/backup@incr.timer /etc/systemd/system/
sudo cp infra/systemd/backup@prune.service /etc/systemd/system/
sudo cp infra/systemd/backup@prune.timer /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение таймеров
sudo systemctl enable --now backup@full.timer
sudo systemctl enable --now backup@incr.timer
sudo systemctl enable --now backup@prune.timer
```

### 5. Создание директории для бэкапов (только для local режима)

```bash
# Создание директории
sudo mkdir -p /opt/clickhouse/backups

# Настройка прав доступа
sudo chown -R clickhouse:clickhouse /opt/clickhouse/backups
sudo chmod -R 755 /opt/clickhouse/backups
```

## Проверка работы

### 1. Ручной запуск бэкапа

```bash
# Полный бэкап
./ops/backup_full.sh s3  # или local

# Инкрементальный бэкап
./ops/backup_incr.sh s3  # или local
```

### 2. Проверка статуса бэкапов

```sql
-- Просмотр последних бэкапов
SELECT 
    backup_name,
    mode,
    status,
    bytes / 1024 / 1024 as size_mb,
    duration_ms / 1000 as duration_sec,
    ts
FROM meta.backup_runs
ORDER BY ts DESC
LIMIT 10;
```

### 3. Верификация бэкапов

```bash
# Полная верификация
./ops/backup_verify.py

# Проверка в формате JSON
./ops/backup_verify.py --json
```

### 4. Тестовое восстановление

```bash
# Восстановление последнего бэкапа
./ops/restore_test.sh

# Восстановление конкретного бэкапа
./ops/restore_test.sh chbk_20251011_023000_full s3
```

## Мониторинг

### 1. Проверка таймеров

```bash
# Просмотр активных таймеров
systemctl list-timers | grep backup

# Просмотр логов
journalctl -u backup@full.service -f
journalctl -u backup@incr.service -f
```

### 2. Метрики в DataLens

Создайте дашборд в DataLens на основе таблицы `meta.backup_runs`:

1. **Статус бэкапов**
   ```sql
   SELECT 
       toDate(ts) as date,
       status,
       count() as count
   FROM meta.backup_runs
   WHERE ts >= today() - 30
   GROUP BY date, status
   ORDER BY date
   ```

2. **Размеры бэкапов**
   ```sql
   SELECT 
       toDate(ts) as date,
       mode,
       sum(bytes) / 1024 / 1024 as size_mb
   FROM meta.backup_runs
   WHERE status = 'ok' AND ts >= today() - 30
   GROUP BY date, mode
   ORDER BY date
   ```

### 3. Алерты

Настройте алерты на основе следующих запросов:

1. **Отсутствие бэкапов за 24 часа**
   ```sql
   SELECT count() = 0
   FROM meta.backup_runs
   WHERE status = 'ok' 
     AND mode = 'full' 
     AND ts >= now() - INTERVAL 1 DAY
   ```

2. **Последний бэкап завершился с ошибкой**
   ```sql
   SELECT status = 'fail'
   FROM meta.backup_runs
   ORDER BY ts DESC
   LIMIT 1
   ```

## Устранение проблем

### Проблема: Ошибка аутентификации ClickHouse

**Решение**:
```bash
# Проверьте пароль в .env
echo $CLICKHOUSE_BACKUP_USER_PASSWORD

# Проверьте подключение
clickhouse-client --host localhost --port 8123 --user backup_user --password $CLICKHOUSE_BACKUP_USER_PASSWORD --query "SELECT 1"
```

### Проблема: Ошибка доступа к S3

**Решение**:
```bash
# Проверьте конфигурацию aws-cli
aws s3 ls

# Проверьте права доступа к бакету
aws s3 ls s3://your-backup-bucket
```

### Проблема: Недостаточно места (local режим)

**Решение**:
```bash
# Проверьте свободное место
df -h /opt/clickhouse/backups

# Очистите старые бэкапы
./ops/backup_prune.sh local
```

## Обслуживание

### Ежемесячно

1. Проверка логов на наличие ошибок
2. Тестовое восстановление
3. Обновление документации

### Квартально

1. Полная проверка бэкапов
2. Тестирование восстановления на новом сервере
3. Обновление политик хранения

## Контакты

- **DevOps**: devops@example.com
- **Инженер данных**: data@example.com
- **Экстренная связь**: +7-XXX-XXX-XX-XX