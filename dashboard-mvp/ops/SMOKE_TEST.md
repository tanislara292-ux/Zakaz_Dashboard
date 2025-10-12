# Smoke-тестирование системы интеграций

## Назначение

Smoke-тестирование для проверки работоспособности всех компонентов системы интеграций Zakaz Dashboard.

## Компоненты

- `smoke_test_integrations.py` - основной скрипт smoke-тестирования
- `run_smoke_test.sh` - обертка для запуска тестов
- `systemd/smoke_test_integrations.service` - systemd сервис для тестов

## Запуск тестов

### 1. Запуск smoke-тестов

```bash
# Перейти в директорию проекта
cd /opt/zakaz_dashboard

# Запуск smoke-тестов
python3 ops/smoke_test_integrations.py

# Запуск с сохранением результатов
python3 ops/smoke_test_integrations.py --output logs/smoke_test_$(date +%Y%m%d_%H%M%S).json

# Запуск с подробным выводом
python3 ops/smoke_test_integrations.py --verbose
```

### 2. Использование обертки

```bash
# Запуск smoke-тестов
./ops/run_smoke_test.sh run

# Запуск с сохранением результатов
./ops/run_smoke_test.sh run-with-results

# Запуск для CI/CD
./ops/run_smoke_test.sh ci

# Проверка здоровья системы
./ops/run_smoke_test.sh health
```

### 3. Запуск через systemd

```bash
# Запуск smoke-тестов
sudo systemctl start smoke_test_integrations.service

# Просмотр логов
sudo journalctl -u smoke_test_integrations.service -n 100

# Запуск по расписанию (если настроен таймер)
sudo systemctl enable smoke_test_integrations.timer
sudo systemctl start smoke_test_integrations.timer
```

## Проверяемые компоненты

### 1. Инфраструктура
- Подключение к ClickHouse
- Наличие необходимых таблиц
- Наличие необходимых представлений

### 2. Данные
- Свежесть данных (отставание не более 2 дней)
- Качество данных о продажах
- Качество маркетинговых данных

### 3. Процессы
- Статус запусков задач
- Система алертов
- Обработка ошибок

## Результаты тестов

### Статусы

- ✅ **ok** - компонент работает нормально
- ⚠️ **warning** - есть предупреждения, но система работоспособна
- ❌ **error** - обнаружены проблемы, требующие внимания

### Пример вывода

```
✅ ClickHouse Connection: ClickHouse доступен
✅ Tables Existence: Все необходимые таблицы существуют
✅ Views Existence: Все необходимые представления существуют
✅ Data Freshness: Данные свежие
⚠️ Job Runs: Есть неудачные запуски: 1
✅ Alerts System: Система алертов работает нормально
✅ Sales Data Quality: Данные о продажах качественные
✅ Marketing Data Quality: Маркетинговые данные качественные

✅ Smoke-тестирование завершено: 7/8 тестов пройдено
Длительность: 2.45 секунд
⚠️ Есть 1 предупреждений
```

### Формат результатов JSON

```json
{
  "overall_status": "warning",
  "timestamp": "2023-10-12T10:00:00+03:00",
  "duration_seconds": 2.45,
  "tests": {
    "total": 8,
    "passed": 7,
    "failed": 0,
    "warnings": 1
  },
  "results": [
    {
      "test_name": "ClickHouse Connection",
      "status": "ok",
      "message": "ClickHouse доступен",
      "timestamp": "2023-10-12T10:00:00+03:00",
      "details": {
        "result": 1
      },
      "duration": 0.05
    },
    ...
  ]
}
```

## Интеграция с CI/CD

### GitHub Actions

```yaml
name: Smoke Tests

on: [push, pull_request]

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v3
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install clickhouse-connect python-dotenv
      
      - name: Run smoke tests
        run: |
          python ops/smoke_test_integrations.py --output smoke_test_results.json
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: smoke-test-results
          path: smoke_test_results.json
```

### Jenkins

```groovy
pipeline {
    agent any
    
    stages {
        stage('Smoke Tests') {
            steps {
                sh 'python ops/smoke_test_integrations.py --output smoke_test_results.json'
                archiveArtifacts artifacts: 'smoke_test_results.json'
            }
        }
    }
}
```

## Устранение неполадок

### Проблема: ClickHouse недоступен

**Симптомы**:
- Тест `ClickHouse Connection` завершается с ошибкой
- Ошибка подключения к ClickHouse

**Решение**:
```bash
# Проверить статус ClickHouse
sudo systemctl status clickhouse-server

# Проверить доступность
curl http://localhost:8123/ping

# Перезапустить ClickHouse
sudo systemctl restart clickhouse-server
```

### Проблема: Отсутствуют таблицы

**Симптомы**:
- Тест `Tables Existence` завершается с ошибкой
- Ошибки при выполнении запросов к таблицам

**Решение**:
```bash
# Применить DDL
clickhouse-client --host localhost --port 8123 -u etl_writer --password <password> \
  --query "$(cat infra/clickhouse/init_integrations.sql)"

# Проверить создание таблиц
clickhouse-client --host localhost --port 8123 -u etl_writer --password <password> \
  --query "SHOW TABLES FROM zakaz"
```

### Проблема: Устаревшие данные

**Симптомы**:
- Тест `Data Freshness` показывает предупреждения
- Отставание данных более 2 дней

**Решение**:
```bash
# Проверить статус таймеров
./ops/systemd/manage_timers.sh status

# Проверить логи проблемных загрузчиков
./ops/systemd/manage_timers.sh logs qtickets
./ops/systemd/manage_timers.sh logs vk_ads
./ops/systemd/manage_timers.sh logs direct

# Перезапустить проблемные загрузчики
sudo ./ops/systemd/manage_timers.sh restart qtickets
sudo ./ops/systemd/manage_timers.sh restart vk_ads
sudo ./ops/systemd/manage_timers.sh restart direct
```

### Проблема: Неудачные запуски задач

**Симптомы**:
- Тест `Job Runs` показывает предупреждения
- Ошибки в логах загрузчиков

**Решение**:
```bash
# Просмотреть детали неудачных запусков
SELECT 
    job,
    status,
    started_at,
    finished_at,
    rows_processed,
    message
FROM zakaz.meta_job_runs
WHERE status = 'error'
ORDER BY started_at DESC
LIMIT 10;

# Запустить проблемный загрузчик вручную
python3 integrations/qtickets/loader.py --days 1
```

## Автоматизация

### Настройка регулярного запуска

```bash
# Создание systemd таймера
sudo cp ops/systemd/smoke_test_integrations.service /etc/systemd/system/
sudo cp ops/systemd/smoke_test_integrations.timer /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение таймера (запуск каждые 6 часов)
sudo systemctl enable smoke_test_integrations.timer
sudo systemctl start smoke_test_integrations.timer
```

### Пример файла таймера

```ini
[Unit]
Description=Smoke Test Timer
Requires=smoke_test_integrations.service

[Timer]
OnCalendar=*-*-* 0,6,12,18:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### Интеграция с алертами

```python
# Добавить в ops/alerts/notify.py
def check_smoke_tests():
    """Проверка результатов smoke-тестов."""
    # Запуск smoke-тестов
    result = subprocess.run(
        ['python3', 'ops/smoke_test_integrations.py', '--output', '/tmp/smoke_test.json']],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        # Отправка алерта
        send_email_alert("Smoke-тесты не пройдены", result.stderr)
```

## Метрики

### Ключевые метрики

- **Процент успешных тестов**: ≥ 90%
- **Время выполнения**: ≤ 30 секунд
- **Свежесть данных**: ≤ 2 дня
- **Частота запусков**: каждые 6 часов или по требованию

### Мониторинг в ClickHouse

```sql
-- История smoke-тестов
SELECT 
    'smoke_test' as test_type,
    now() as test_time,
    JSONExtractString(results, 'overall_status') as status,
    JSONExtractInt(results, 'duration_seconds') as duration,
    JSONExtractInt(results, 'tests.total') as total,
    JSONExtractInt(results, 'tests.passed') as passed,
    JSONExtractInt(results, 'tests.failed') as failed,
    JSONExtractInt(results, 'tests.warnings') as warnings
FROM (
    SELECT now() as test_time, 'ok' as status, 0 as duration, 
           8 as total, 8 as passed, 0 as failed, 0 as warnings
)
UNION ALL
-- Здесь можно добавить реальные результаты из логов
```

## Заключение

Smoke-тестирование обеспечивает быструю проверку работоспособности системы интеграций. Регулярное выполнение тестов позволяет оперативно выявлять и устранять проблемы, обеспечивая надежность и стабильность системы.