# =============================================================================
# Qtickets API - ДЕМОНСТРАЦИОННЫЙ ЗАПУСК (с мок данными)
# =============================================================================
# Этот скрипт демонстрирует работу системы тестирования без реального API
# =============================================================================

# Настройки
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$LOG_DIR = ".\logs"
$RESULTS_FILE = ".\demo_test_results_${TIMESTAMP}.json"
$SUMMARY_FILE = ".\demo_test_summary_${TIMESTAMP}.md"

# Создание директории для логов
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

# Счетчики
$TotalTests = 0
$PassedTests = 0
$FailedTests = 0

Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Qtickets API - ДЕМОНСТРАЦИОННЫЙ ЗАПУСК" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Время начала: $(Get-Date)"
Write-Host "Режим: Демонстрация с мок данными"
Write-Host "========================================="

# Мок данные для демонстрации
$MockResponses = @{
    "1.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 4360; payed = 1; total = 1500.00 }); pagination = @{ current_page = 1; total = 1; per_page = 20 } } }
    "1.2" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 4360; payed = 1; status = "paid" }); filters = @{ where = @(@{ column = "payed"; value = 1 }) } } }
    "1.3" = @{ status = 200; data = @{ status = "success"; data = @() } }
    "1.4" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 4360; created_at = "2025-11-06T10:30:00+03:00" }) } }
    "1.5" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 4360; payed = 1; total = 1500.00 }) } }
    "1.6" = @{ status = 200; data = @{ status = "success"; data = @{ id = 4360; payed = 1; total = 1500.00; client = @{ id = 235; name = "Иван"; surname = "Иванов" } } } }
    "1.7" = @{ status = 200; data = @{ status = "success"; message = "Билет успешно удален" } }
    "1.8" = @{ status = 200; data = @{ status = "success"; data = @{ id = 63993; client_name = "Иван"; client_surname = "Петров" } } }
    "1.9" = @{ status = 200; data = @{ status = "success"; data = @{ id = 63993; amount = 1500.00; deduction_amount = 100.00; refund_amount = 1400.00 } } }
    "1.10" = @{ status = 200; data = @{ status = "success"; data = @{ id = 4360; status = "restored" } } }

    "2.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 235; name = "Иван"; surname = "Иванов"; email = "ivan@example.com" }) } }
    "2.2" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 235; name = "Иван" }); pagination = @{ current_page = 1; per_page = 10 } } }
    "2.3" = @{ status = 201; data = @{ status = "success"; data = @{ id = 236; email = "test_client@example.com"; name = "Тестовый"; surname = "Клиент" } } }
    "2.4" = @{ status = 200; data = @{ status = "success"; data = @{ id = 235; name = "Иван"; phone = "+79991234567" } } }

    "3.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 12; name = "Концерт симфонического оркестра" }, @{ id = 33; name = "Театральная постановка" }) } }
    "3.2" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 12; name = "Концерт"; status = "active" }) } }
    "3.3" = @{ status = 200; data = @{ status = "success"; data = @{ id = 33; name = "Театральная постановка"; description = "Современная драма"; start_date = "2025-11-20T18:30:00+03:00" } } }
    "3.4" = @{ status = 200; data = @{ status = "success"; data = @{ id = 12; name = "Концерт симфонического оркестра"; description = "Вечер классической музыки" } } }
    "3.5" = @{ status = 201; data = @{ status = "success"; data = @{ id = 34; name = "Тестовое мероприятие API"; description = "Создано через API тестирование" } } }
    "3.6" = @{ status = 200; data = @{ status = "success"; data = @{ id = 33; name = "Театральная постановка (обновлено)"; description = "Описание обновлено через API" } } }
    "3.7" = @{ status = 200; data = @{ status = "success"; data = @(@{ seat_id = "CENTER_PARTERRE-20;5"; row = 20; seat = 5; price = 1500.00; status = "available" }, @{ seat_id = "CENTER_PARTERRE-20;6"; row = 20; seat = 6; price = 1500.00; status = "sold" }) } }

    "4.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 1; name = "Стандартный"; color = "#000000" }, @{ id = 2; name = "VIP"; color = "#FFD700" }) } }
    "4.2" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 1; name = "Студенческий"; value = 30; type = "percentage" }) } }
    "4.3" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 1; code = "WELCOME2025"; discount_type = "percentage"; discount_value = 10 }) } }
    "4.4" = @{ status = 201; data = @{ status = "success"; data = @{ id = 2; code = "TESTPROMO_20251107"; discount_type = "percentage"; discount_value = 10 } } }
    "4.5" = @{ status = 200; data = @{ status = "success"; data = @{ id = 1; discount_value = 15; valid_to = "2025-12-31T23:59:59+03:00" } } }

    "5.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63993; barcode = "872964136579"; order_id = 4360; scanned = false }) } }
    "5.2" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63993; event_id = 33; barcode = "872964136579" }) } }
    "5.3" = @{ status = 200; data = @{ status = "success"; data = @{ id = 63993; scanned = false; scanned_at = $null } } }
    "5.4" = @{ status = 200; data = @{ status = "success"; data = @{ id = 63993; scanned = true; scanned_at = "2025-11-07T12:00:00+03:00" } } }
    "5.5" = @{ status = 200; data = @{ status = "success"; data = @{ processed = 2; successful = 2 } } }

    "6.1" = @{ status = 201; data = @{ status = "success"; data = @{ id = 63995; external_id = "test_ticket_20251107"; barcode = "872964136581" } } }
    "6.2" = @{ status = 201; data = @{ status = "success"; data = @{ processed = 2; successful = 2; tickets = @(@{ id = 63996 }, @{ id = 63997 }) } } }
    "6.3" = @{ status = 201; data = @{ status = "success"; data = @{ id = 63998; reserved_to = "2025-11-07T18:00:00+03:00" } } }
    "6.4" = @{ status = 200; data = @{ status = "success"; data = @{ id = 63993; paid = true; paid_at = "2025-11-07T12:00:00+03:00" } } }
    "6.5" = @{ status = 200; data = @{ status = "success"; data = @{ processed = 2; successful = 2 } } }
    "6.6" = @{ status = 200; data = @{ status = "success"; message = "Билет успешно удален" } }
    "6.7" = @{ status = 200; data = @{ status = "success"; message = "Билеты успешно удалены"; deleted_count = 2 } }
    "6.8" = @{ status = 200; data = @{ status = "success"; data = @(@{ seat_id = "CENTER_PARTERRE-20;5"; available = false; status = "sold" }, @{ seat_id = "CENTER_PARTERRE-20;6"; available = true; status = "available" }) } }
    "6.9" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63994; external_order_id = "order67890" }) } }
    "6.10" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63994; event_id = 12; external_order_id = "order67890" }) } }
    "6.11" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63994; event_id = 12; show_id = 4076; external_order_id = "order67890" }) } }
    "6.12" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63993; barcode = "872964136579" }) } }
    "6.13" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63993; barcode = "872964136579"; external_order_id = "order67890" }) } }
    "6.14" = @{ status = 200; data = @{ status = "success"; data = @(@{ seat_id = "CENTER_PARTERRE-20;5"; available = true }) } }
    "6.15" = @{ status = 200; data = @{ status = "success"; data = @(@{ seat_id = "CENTER_PARTERRE-20;5"; show_id = 4076; available = true }) } }

    "7.1" = @{ status = 401; data = @{ status = "error"; error = "WRONG_AUTHORIZATION"; message = "Неверный токен авторизации" } }
    "7.2" = @{ status = 404; data = @{ status = "error"; error = "ORDER_NOT_FOUND"; message = "Заказ не найден" } }
    "7.3" = @{ status = 404; data = @{ status = "error"; error = "EVENT_NOT_FOUND"; message = "Мероприятие не найдено" } }
    "7.4" = @{ status = 400; data = @{ status = "error"; error = "VALIDATION_ERROR"; message = "Ошибка валидации данных" } }
    "7.5" = @{ status = 400; data = @{ status = "error"; error = "VALIDATION_ERROR"; message = "Некорректные параметры запроса" } }
}

# Тесты для демонстрации
$TestScenarios = @(
    @{ Number = "1.1"; Category = "ЗАКАЗЫ"; Name = "Получить список всех заказов"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders" }
    @{ Number = "1.2"; Category = "ЗАКАЗЫ"; Name = "Получить список оплаченных заказов"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders" }
    @{ Number = "1.6"; Category = "ЗАКАЗЫ"; Name = "Получить данные конкретного заказа #4360"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders/4360" }
    @{ Number = "2.1"; Category = "ПОКУПАТЕЛИ"; Name = "Получить список покупателей"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/clients" }
    @{ Number = "2.3"; Category = "ПОКУПАТЕЛИ"; Name = "Создать покупателя"; Method = "POST"; URL = "https://qtickets.ru/api/rest/v1/clients" }
    @{ Number = "3.1"; Category = "МЕРОПРИЯТИЯ"; Name = "Получить список мероприятий"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events" }
    @{ Number = "3.3"; Category = "МЕРОПРИЯТИЯ"; Name = "Получить данные конкретного мероприятия #33"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events/33" }
    @{ Number = "4.1"; Category = "СКИДКИ_И_ПРОМОКОДЫ"; Name = "Получить список оттенков для цен"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/discounts/colors" }
    @{ Number = "5.1"; Category = "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ"; Name = "Получить список штрихкодов билетов"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/barcodes" }
    @{ Number = "6.1"; Category = "ПАРТНЕРСКИЙ_API"; Name = "Добавить билеты (одиночный)"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/add" }
    @{ Number = "6.8"; Category = "ПАРТНЕРСКИЙ_API"; Name = "Проверить статусы мест (пакетный)"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/check/12/4076" }
    @{ Number = "6.12"; Category = "ПАРТНЕРСКИЙ_API"; Name = "Поиск билетов по штрихкоду"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/find" }
    @{ Number = "7.1"; Category = "ТЕСТЫ_ОШИБОК"; Name = "Проверка авторизации (с неверным токеном)"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events" }
    @{ Number = "7.2"; Category = "ТЕСТЫ_ОШИБОК"; Name = "Проверка несуществующего заказа"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders/999999999" }
    @{ Number = "7.4"; Category = "ТЕСТЫ_ОШИБОК"; Name = "Проверка с пустым телом где требуется"; Method = "POST"; URL = "https://qtickets.ru/api/rest/v1/clients" }
)

# Выполнение демонстрационных тестов
foreach ($Test in $TestScenarios) {
    $TotalTests++

    Write-Host "`n🔍 Выполняю: $($Test.Name)" -ForegroundColor Yellow
    Start-Sleep -Milliseconds 500  # Имитация задержки сети

    $MockResponse = $MockResponses[$Test.Number]
    $StatusCode = $MockResponse.status
    $ResponseData = $MockResponse.data | ConvertTo-Json -Depth 10 -Compress

    # Логирование
    $LogEntry = @{
        test_number = $Test.Number
        test_category = $Test.Category
        test_name = $Test.Name
        method = $Test.Method
        url = $Test.URL
        headers = @{"Authorization" = "Bearer DEMO_TOKEN_***"}
        body = if ($Test.Method -eq "POST") { '{"demo": "data"}' } else { "" }
        response = $ResponseData
        status_code = $StatusCode
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    } | ConvertTo-Json -Depth 10

    # Сохранение в файл
    Add-Content -Path $RESULTS_FILE -Value ","
    Add-Content -Path $RESULTS_FILE -Value $LogEntry

    # Вывод результата
    if ($StatusCode -ge 200 -and $StatusCode -lt 300) {
        Write-Host "✅ Тест $($Test.Number): $($Test.Name) ($StatusCode)" -ForegroundColor Green
        $PassedTests++
    } else {
        Write-Host "❌ Тест $($Test.Number): $($Test.Name) ($StatusCode)" -ForegroundColor Red
        $FailedTests++
    }

    # Детальный лог
    $LogFileName = "test_$($Test.Number -replace '\.', '_')_$($Test.Name -replace ' ', '_').log"
    $LogPath = Join-Path $LOG_DIR $LogFileName

    @"
========================================
ТЕСТ $($Test.Number): $($Test.Name)
Категория: $($Test.Category)
Метод: $($Test.Method)
URL: $($Test.URL)
Headers: {"Authorization": "Bearer DEMO_TOKEN_***"}
Body: $(if ($Test.Method -eq "POST") { '{"demo": "data"}' } else { '' })
Status Code: $StatusCode
Response:
$ResponseData
========================================
"@ | Out-File -FilePath $LogPath -Encoding UTF8
}

# Создание отчета
$SuccessRate = if ($TotalTests -gt 0) { [math]::Round(($PassedTests / $TotalTests) * 100, 2) } else { 0 }

$Report = @"
# 📊 ДЕМОНСТРАЦИОННЫЙ ОТЧЕТ О ТЕСТИРОВАНИИ Q TICKETS API

## 📋 ОБЩАЯ ИНФОРМАЦИЯ

- **Дата тестирования:** $(Get-Date)
- **Режим:** Демонстрация с мок данными
- **Цель:** Показать работу системы тестирования
- **API Токен:** DEMO_TOKEN_***

## 📊 СТАТИСТИКА ТЕСТИРОВАНИЯ

| Метрика | Значение |
|---------|---------|
| Всего тестов | $TotalTests |
| Успешных | $PassedTests |
| Неудачных | $FailedTests |
| % Успешности | $SuccessRate% |

## 📈 РЕЗУЛЬТАТЫ ПО КАТЕГОРИЯМ

### 🎪 ЗАКАЗЫ (ORDERS)
✅ Тест 1.1: Получить список всех заказов (200)
✅ Тест 1.2: Получить список оплаченных заказов (200)
✅ Т�试 1.6: Получить данные конкретного заказа #4360 (200)

### 👥 ПОКУПАТЕЛИ (CLIENTS)
✅ Тест 2.1: Получить список покупателей (200)
✅ Тест 2.3: Создать покупателя (201)

### 🎭 МЕРОПРИЯТИЯ (EVENTS)
✅ Тест 3.1: Получить список мероприятий (200)
✅ Тест 3.3: Получить данные конкретного мероприятия #33 (200)

### 🎫 СКИДКИ И ПРОМОКОДЫ
✅ Тест 4.1: Получить список оттенков для цен (200)

### 📊 ШТРИХКОДЫ И СКАНИРОВАНИЕ
✅ Тест 5.1: Получить список штрихкодов билетов (200)

### 🤝 ПАРТНЕРСКИЙ API
✅ Тест 6.1: Добавить билеты (одиночный) (201)
✅ Тест 6.8: Проверить статусы мест (пакетный) (200)
✅ Тест 6.12: Поиск билетов по штрихкоду (200)

### ⚠️ ТЕСТЫ ОШИБОК
❌ Тест 7.1: Проверка авторизации (с неверным токеном) (401)
❌ Тест 7.2: Проверка несуществующего заказа (404)
❌ Тест 7.4: Проверка с пустым телом где требуется (400)

## 📋 ДЕТАЛЬНЫЕ ПРИМЕРЫ ОТВЕТОВ

### ✅ Успешный ответ (GET /orders)
\`\`\`json
$($MockResponses["1.1"].data | ConvertTo-Json -Depth 10)
\`\`\`

### ✅ Успешный ответ (POST /clients)
\`\`\`json
$($MockResponses["2.3"].data | ConvertTo-Json -Depth 10)
\`\`\`

### ❌ Ответ с ошибкой (GET /events с неверным токеном)
\`\`\`json
$($MockResponses["7.1"].data | ConvertTo-Json -Depth 10)
\`\`\`

## 📂 ФАЙЛЫ ТЕСТИРОВАНИЯ

- **Полные результаты:** \`$RESULTS_FILE\`
- **Логи по каждому тесту:** \`$LOG_DIR/\`

## 🛠️ СЛЕДУЮЩИЕ ШАГИ

1. **Получите реальный API токен** в личном кабинете Qtickets
2. **Запустите полный тест:** \`.\run_tests.ps1 YOUR_API_TOKEN\`
3. **Изучите реальные ответы** API
4. **Адаптируйте ID** под вашу систему

## 📝 ЗАКЛЮЧЕНИЕ

Демонстрация завершена успешно! Система готова к полноценному тестированию.

**Для реального тестирования используйте:** \`.\run_tests.ps1 YOUR_API_TOKEN\`

**Время завершения:** $(Get-Date)
"@

$Report | Out-File -FilePath $SUMMARY_FILE -Encoding UTF8

# Финальная статистика
Write-Host "`n=========================================" -ForegroundColor Blue
Write-Host "ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "📊 СТАТИСТИКА:" -ForegroundColor Yellow
Write-Host "   Всего тестов: $TotalTests"
Write-Host "   ✅ Успешных: $PassedTests" -ForegroundColor Green
Write-Host "   ❌ Неудачных: $FailedTests" -ForegroundColor Red
Write-Host "   📈 Успешность: $SuccessRate%" -ForegroundColor Yellow
Write-Host "📂 ФАЙЛЫ:" -ForegroundColor Yellow
Write-Host "   📄 Отчет: $SUMMARY_FILE"
Write-Host "   📊 Результаты: $RESULTS_FILE"
Write-Host "   📋 Логи: $LOG_DIR/"
Write-Host "========================================="
Write-Host ""
Write-Host "🎉 Демонстрационный запуск завершен!" -ForegroundColor Green
Write-Host "📝 Просмотрите отчет: $SUMMARY_FILE" -ForegroundColor Cyan
Write-Host "🚀 Для реального тестирования: .\run_tests.ps1 YOUR_API_TOKEN" -ForegroundColor Yellow
Write-Host "========================================="
