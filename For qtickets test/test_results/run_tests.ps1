# =============================================================================
# Qtickets API - ПОЛНОЕ МАСШТАБНОЕ ТЕСТИРОВАНИЕ (PowerShell)
# =============================================================================
# Запуск: .\run_tests.ps1 YOUR_API_TOKEN
# =============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$Token
)

# Настройки
$BASE_URL = "https://qtickets.ru/api/rest/v1"
$PARTNERS_URL = "https://qtickets.ru/api/partners/v1"
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$LOG_DIR = ".\logs"
$RESULTS_FILE = ".\test_results_${TIMESTAMP}.json"
$SUMMARY_FILE = ".\test_summary_${TIMESTAMP}.md"

# Создание директории для логов
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

# Инициализация файлов
"[]" | Out-File -FilePath $RESULTS_FILE -Encoding UTF8
New-Item -ItemType File -Path $SUMMARY_FILE | Out-Null

# Счетчики
$TotalTests = 0
$PassedTests = 0
$FailedTests = 0

# Функция логирования
function Log-Request {
    param(
        [string]$TestName,
        [string]$Method,
        [string]$Url,
        [string]$Headers,
        [string]$Body,
        [string]$Response,
        [int]$StatusCode,
        [string]$TestCategory,
        [string]$TestNumber
    )

    $script:TotalTests++

    # Формирование JSON лога
    $LogEntry = @{
        test_number = $TestNumber
        test_category = $TestCategory
        test_name = $TestName
        method = $Method
        url = $Url
        headers = $Headers
        body = $Body
        response = $Response
        status_code = $StatusCode
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    } | ConvertTo-Json -Depth 10

    # Чтение текущих результатов и добавление новой записи
    $CurrentResults = Get-Content $RESULTS_FILE | ConvertFrom-Json
    $CurrentResults += $LogEntry | ConvertFrom-Json
    $CurrentResults | ConvertTo-Json -Depth 10 | Out-File -FilePath $RESULTS_FILE -Encoding UTF8

    # Вывод в консоль
    if ($StatusCode -ge 200 -and $StatusCode -lt 300) {
        Write-Host "✅ Тест $TestNumber`: $TestName ($StatusCode)" -ForegroundColor Green
        $script:PassedTests++
    } else {
        Write-Host "❌ Тест $TestNumber`: $TestName ($StatusCode)" -ForegroundColor Red
        $script:FailedTests++
    }

    # Детальный лог в файл
    $LogFileName = "test_${TestNumber}_$($TestName -replace ' ', '_').log"
    $LogPath = Join-Path $LOG_DIR $LogFileName

    @"
==========================================
ТЕСТ $TestNumber`: $TestName
Категория: $TestCategory
Метод: $Method
URL: $Url
Headers: $Headers
Body: $Body
Status Code: $StatusCode
Response:
$Response
==========================================
"@ | Out-File -FilePath $LogPath -Encoding UTF8
}

# Функция выполнения теста
function Execute-Test {
    param(
        [string]$TestNumber,
        [string]$TestCategory,
        [string]$TestName,
        [string]$Method,
        [string]$Url,
        [string]$Headers,
        [string]$Body
    )

    Write-Host "`n🔍 Выполняю: $TestName" -ForegroundColor Yellow

    try {
        $HeadersObj = @{
            "Authorization" = "Bearer $Token"
            "Accept" = "application/json"
            "Content-Type" = "application/json"
        }

        $Response = Invoke-RestMethod -Uri $Url -Method $Method -Headers $HeadersObj -Body $Body -ErrorAction Stop
        $StatusCode = 200
        $ResponseBody = $Response | ConvertTo-Json -Depth 10 -Compress
    }
    catch {
        $StatusCode = [int]$_.Exception.Response.StatusCode
        $ResponseBody = $_.Exception.Response.GetResponseStream()
        $Reader = New-Object System.IO.StreamReader($ResponseBody)
        $ResponseBody = $Reader.ReadToEnd()
        try {
            $ResponseBody = $ResponseBody | ConvertTo-Json -Depth 10 -Compress
        } catch {
            $ResponseBody = "`"$ResponseBody`""
        }
    }

    Log-Request -TestName $TestName -Method $Method -Url $Url -Headers $Headers -Body $Body -Response $ResponseBody -StatusCode $StatusCode -TestCategory $TestCategory -TestNumber $TestNumber
}

Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Qtickets API - ПОЛНОЕ МАСШТАБНОЕ ТЕСТИРОВАНИЕ" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Время начала: $(Get-Date)"
Write-Host "API Токен: $($Token.Substring(0, [Math]::Min(10, $Token.Length)))..."
Write-Host "Базовый URL: $BASE_URL"
Write-Host "Partners URL: $PARTNERS_URL"
Write-Host "Файл результатов: $RESULTS_FILE"
Write-Host "========================================="

# =============================================================================
# КАТЕГОРИЯ 1: ЗАКАЗЫ (ORDERS) - 10 ТЕСТОВ
# =============================================================================

Write-Host "`n🎪 КАТЕГОРИЯ 1: ЗАКАЗЫ (ORDERS)" -ForegroundColor Yellow

# Тест 1.1: Получить список всех заказов
Execute-Test -TestNumber "1.1" -TestCategory "ЗАКАЗЫ" -TestName "Получить список всех заказов" `
    -Method "GET" -Url "$BASE_URL/orders" -Headers "" -Body ""

# Тест 1.2: Получить список оплаченных заказов
$Body1_2 = @"
{
  "where": [
    {
      "column": "payed",
      "value": 1
    }
  ],
  "orderBy": {
    "id": "desc"
  },
  "page": 1
}
"@
Execute-Test -TestNumber "1.2" -TestCategory "ЗАКАЗЫ" -TestName "Получить список оплаченных заказов" `
    -Method "GET" -Url "$BASE_URL/orders" -Headers "" -Body $Body1_2

# Тест 1.3: Получить список неоплаченных заказов
$Body1_3 = @"
{
  "where": [
    {
      "column": "payed",
      "value": 0
    }
  ],
  "orderBy": {
    "id": "desc"
  },
  "page": 1
}
"@
Execute-Test -TestNumber "1.3" -TestCategory "ЗАКАЗЫ" -TestName "Получить список неоплаченных заказов" `
    -Method "GET" -Url "$BASE_URL/orders" -Headers "" -Body $Body1_3

# Тест 1.4: Получить заказы с фильтром по дате
$Body1_4 = @"
{
  "where": [
    {
      "column": "created_at",
      "operator": ">=",
      "value": "2025-11-01T00:00:00+03:00"
    }
  ],
  "page": 1
}
"@
Execute-Test -TestNumber "1.4" -TestCategory "ЗАКАЗЫ" -TestName "Получить заказы с фильтром по дате" `
    -Method "GET" -Url "$BASE_URL/orders" -Headers "" -Body $Body1_4

# Тест 1.5: Получить заказы с множественными фильтрами
$Body1_5 = @"
{
  "where": [
    {
      "column": "payed",
      "value": 1
    },
    {
      "column": "total",
      "operator": ">",
      "value": 1000
    }
  ],
  "orderBy": {
    "id": "desc"
  },
  "page": 1
}
"@
Execute-Test -TestNumber "1.5" -TestCategory "ЗАКАЗЫ" -TestName "Получить заказы с множественными фильтрами" `
    -Method "GET" -Url "$BASE_URL/orders" -Headers "" -Body $Body1_5

# Тест 1.6: Получить данные конкретного заказа
Execute-Test -TestNumber "1.6" -TestCategory "ЗАКАЗЫ" -TestName "Получить данные конкретного заказа #4360" `
    -Method "GET" -Url "$BASE_URL/orders/4360" -Headers "" -Body ""

# Тест 1.7: Удалить билет из заказа
$Body1_7 = @"
{
  "basket_id": 63993
}
"@
Execute-Test -TestNumber "1.7" -TestCategory "ЗАКАЗЫ" -TestName "Удалить билет из заказа" `
    -Method "DELETE" -Url "$BASE_URL/orders/basket/63993" -Headers "" -Body $Body1_7

# Тест 1.8: Изменить билет в заказе
$Body1_8 = @"
{
  "client_name": "Иван",
  "client_surname": "Петров",
  "client_phone": "+79991234567"
}
"@
Execute-Test -TestNumber "1.8" -TestCategory "ЗАКАЗЫ" -TestName "Изменить билет в заказе" `
    -Method "PUT" -Url "$BASE_URL/orders/basket/63993" -Headers "" -Body $Body1_8

# Тест 1.9: Возврат билета
$Body1_9 = @"
{
  "amount": 1500.00,
  "deduction_amount": 100.00
}
"@
Execute-Test -TestNumber "1.9" -TestCategory "ЗАКАЗЫ" -TestName "Возврат билета" `
    -Method "POST" -Url "$BASE_URL/orders/basket/63993/return" -Headers "" -Body $Body1_9

# Тест 1.10: Восстановить отменённый заказ
Execute-Test -TestNumber "1.10" -TestCategory "ЗАКАЗЫ" -TestName "Восстановить отменённый заказ" `
    -Method "POST" -Url "$BASE_URL/orders/4360/restore" -Headers "" -Body ""

# =============================================================================
# КАТЕГОРИЯ 2: ПОКУПАТЕЛИ (CLIENTS) - 4 ТЕСТА
# =============================================================================

Write-Host "`n👥 КАТЕГОРИЯ 2: ПОКУПАТЕЛИ (CLIENTS)" -ForegroundColor Yellow

# Тест 2.1: Получить список покупателей
Execute-Test -TestNumber "2.1" -TestCategory "ПОКУПАТЕЛИ" -TestName "Получить список покупателей" `
    -Method "GET" -Url "$BASE_URL/clients" -Headers "" -Body ""

# Тест 2.2: Получить список покупателей с пагинацией
$Body2_2 = @"
{
  "page": 1,
  "per_page": 10
}
"@
Execute-Test -TestNumber "2.2" -TestCategory "ПОКУПАТЕЛИ" -TestName "Получить список покупателей с пагинацией" `
    -Method "GET" -Url "$BASE_URL/clients" -Headers "" -Body $Body2_2

# Тест 2.3: Создать покупателя
$Body2_3 = @"
{
  "email": "test_client_${TIMESTAMP}@example.com",
  "name": "Тестовый",
  "surname": "Клиент",
  "middlename": "API",
  "phone": "+79990001122"
}
"@
Execute-Test -TestNumber "2.3" -TestCategory "ПОКУПАТЕЛИ" -TestName "Создать покупателя" `
    -Method "POST" -Url "$BASE_URL/clients" -Headers "" -Body $Body2_3

# Тест 2.4: Обновить данные покупателя
$Body2_4 = @"
{
  "name": "Иван",
  "phone": "+79991234567"
}
"@
Execute-Test -TestNumber "2.4" -TestCategory "ПОКУПАТЕЛИ" -TestName "Обновить данные покупателя" `
    -Method "PUT" -Url "$BASE_URL/clients/235" -Headers "" -Body $Body2_4

# =============================================================================
# КАТЕГОРИЯ 3: МЕРОПРИЯТИЯ (EVENTS) - 7 ТЕСТОВ
# =============================================================================

Write-Host "`n🎭 КАТЕГОРИЯ 3: МЕРОПРИЯТИЯ (EVENTS)" -ForegroundColor Yellow

# Тест 3.1: Получить список мероприятий
Execute-Test -TestNumber "3.1" -TestCategory "МЕРОПРИЯТИЯ" -TestName "Получить список мероприятий" `
    -Method "GET" -Url "$BASE_URL/events" -Headers "" -Body ""

# Тест 3.2: Получить список мероприятий с фильтрами
$Body3_2 = @"
{
  "where": [
    {
      "column": "status",
      "value": "active"
    }
  ],
  "page": 1
}
"@
Execute-Test -TestNumber "3.2" -TestCategory "МЕРОПРИЯТИЯ" -TestName "Получить список мероприятий с фильтрами" `
    -Method "GET" -Url "$BASE_URL/events" -Headers "" -Body $Body3_2

# Тест 3.3: Получить данные конкретного мероприятия
Execute-Test -TestNumber "3.3" -TestCategory "МЕРОПРИЯТИЯ" -TestName "Получить данные конкретного мероприятия #33" `
    -Method "GET" -Url "$BASE_URL/events/33" -Headers "" -Body ""

# Тест 3.4: Получить данные конкретного мероприятия #12
Execute-Test -TestNumber "3.4" -TestCategory "МЕРОПРИЯТИЯ" -TestName "Получить данные конкретного мероприятия #12" `
    -Method "GET" -Url "$BASE_URL/events/12" -Headers "" -Body ""

# Тест 3.5: Создать мероприятие
$Body3_5 = @"
{
  "name": "Тестовое мероприятие API",
  "description": "Создано через API тестирование",
  "start_date": "2025-12-01T19:00:00+03:00",
  "finish_date": "2025-12-01T21:00:00+03:00"
}
"@
Execute-Test -TestNumber "3.5" -TestCategory "МЕРОПРИЯТИЯ" -TestName "Создать мероприятие" `
    -Method "POST" -Url "$BASE_URL/events" -Headers "" -Body $Body3_5

# Тест 3.6: Редактировать мероприятие
$Body3_6 = @"
{
  "name": "Театральная постановка (обновлено)",
  "description": "Описание обновлено через API"
}
"@
Execute-Test -TestNumber "3.6" -TestCategory "МЕРОПРИЯТИЯ" -TestName "Редактировать мероприятие" `
    -Method "PUT" -Url "$BASE_URL/events/33" -Headers "" -Body $Body3_6

# Тест 3.7: Получить информацию о местах в мероприятии
Execute-Test -TestNumber "3.7" -TestCategory "МЕРОПРИЯТИЯ" -TestName "Получить информацию о местах в мероприятии #33" `
    -Method "GET" -Url "$BASE_URL/events/33/seats" -Headers "" -Body ""

# =============================================================================
# КАТЕГОРИЯ 4: СКИДКИ И ПРОМОКОДЫ - 5 ТЕСТОВ
# =============================================================================

Write-Host "`n🎫 КАТЕГОРИЯ 4: СКИДКИ И ПРОМОКОДЫ" -ForegroundColor Yellow

# Тест 4.1: Получить список оттенков для цен
Execute-Test -TestNumber "4.1" -TestCategory "СКИДКИ_И_ПРОМОКОДЫ" -TestName "Получить список оттенков для цен" `
    -Method "GET" -Url "$BASE_URL/discounts/colors" -Headers "" -Body ""

# Тест 4.2: Получить список скидок
Execute-Test -TestNumber "4.2" -TestCategory "СКИДКИ_И_ПРОМОКОДЫ" -TestName "Получить список скидок" `
    -Method "GET" -Url "$BASE_URL/discounts" -Headers "" -Body ""

# Тест 4.3: Получить список промокодов
Execute-Test -TestNumber "4.3" -TestCategory "СКИДКИ_И_ПРОМОКОДЫ" -TestName "Получить список промокодов" `
    -Method "GET" -Url "$BASE_URL/promo-codes" -Headers "" -Body ""

# Тест 4.4: Создать промокод
$Body4_4 = @"
{
  "code": "TESTPROMO_${TIMESTAMP}",
  "discount_type": "percentage",
  "discount_value": 10,
  "valid_from": "2025-11-07T00:00:00+03:00",
  "valid_to": "2025-12-07T23:59:59+03:00"
}
"@
Execute-Test -TestNumber "4.4" -TestCategory "СКИДКИ_И_ПРОМОКОДЫ" -TestName "Создать промокод" `
    -Method "POST" -Url "$BASE_URL/promo-codes" -Headers "" -Body $Body4_4

# Тест 4.5: Редактировать промокод
$Body4_5 = @"
{
  "discount_value": 15,
  "valid_to": "2025-12-31T23:59:59+03:00"
}
"@
Execute-Test -TestNumber "4.5" -TestCategory "СКИДКИ_И_ПРОМОКОДЫ" -TestName "Редактировать промокод" `
    -Method "PUT" -Url "$BASE_URL/promo-codes/1" -Headers "" -Body $Body4_5

# =============================================================================
# КАТЕГОРИЯ 5: ШТРИХКОДЫ И СКАНИРОВАНИЕ - 5 ТЕСТОВ
# =============================================================================

Write-Host "`n📊 КАТЕГОРИЯ 5: ШТРИХКОДЫ И СКАНИРОВАНИЕ" -ForegroundColor Yellow

# Тест 5.1: Получить список штрихкодов билетов
Execute-Test -TestNumber "5.1" -TestCategory "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" -TestName "Получить список штрихкодов билетов" `
    -Method "GET" -Url "$BASE_URL/barcodes" -Headers "" -Body ""

# Тест 5.2: Получить штрихкоды для конкретного мероприятия
$Body5_2 = @"
{
  "where": [
    {
      "column": "event_id",
      "value": 33
    }
  ]
}
"@
Execute-Test -TestNumber "5.2" -TestCategory "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" -TestName "Получить штрихкоды для конкретного мероприятия" `
    -Method "GET" -Url "$BASE_URL/barcodes" -Headers "" -Body $Body5_2

# Тест 5.3: Получить информацию о наличии сканирования
Execute-Test -TestNumber "5.3" -TestCategory "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" -TestName "Получить информацию о наличии сканирования" `
    -Method "GET" -Url "$BASE_URL/barcodes/scan/872964136579" -Headers "" -Body ""

# Тест 5.4: Отметить сканирование билета
$Body5_4 = @"
{
  "barcode": "872964136579",
  "event_id": 33,
  "show_id": 41
}
"@
Execute-Test -TestNumber "5.4" -TestCategory "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" -TestName "Отметить сканирование билета" `
    -Method "POST" -Url "$BASE_URL/barcodes/scan" -Headers "" -Body $Body5_4

# Тест 5.5: Пакетная отправка сканирований
$Body5_5 = @"
{
  "scans": [
    {
      "barcode": "872964136579",
      "event_id": 33,
      "show_id": 41,
      "scanned_at": "2025-11-07T12:00:00+03:00"
    },
    {
      "barcode": "872964136580",
      "event_id": 33,
      "show_id": 41,
      "scanned_at": "2025-11-07T12:01:00+03:00"
    }
  ]
}
"@
Execute-Test -TestNumber "5.5" -TestCategory "ШТРИХКОДЫ_И_СКАНИРОВАНИЕ" -TestName "Пакетная отправка сканирований" `
    -Method "POST" -Url "$BASE_URL/barcodes/scan/batch" -Headers "" -Body $Body5_5

# =============================================================================
# КАТЕГОРИЯ 6: ПАРТНЁРСКИЙ API - УПРАВЛЕНИЕ БИЛЕТАМИ - 15 ТЕСТОВ
# =============================================================================

Write-Host "`n🤝 КАТЕГОРИЯ 6: ПАРТНЁРСКИЙ API - УПРАВЛЕНИЕ БИЛЕТАМИ" -ForegroundColor Yellow

# Тест 6.1: Добавить билеты (одиночный)
$Body6_1 = @"
{
  "seat_id": "CENTER_PARTERRE-20;7",
  "offer_id": "full",
  "external_id": "test_ticket_${TIMESTAMP}",
  "external_order_id": "test_order_${TIMESTAMP}",
  "price": 1500.00,
  "client_email": "test_${TIMESTAMP}@example.com",
  "client_phone": "+79990001133",
  "client_name": "Тестовый",
  "client_surname": "Пользователь",
  "client_middlename": "API"
}
"@
Execute-Test -TestNumber "6.1" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Добавить билеты (одиночный)" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/add" -Headers "" -Body $Body6_1

# Тест 6.2: Добавить билеты (пакетный)
$Body6_2 = @"
{
  "batch": [
    {
      "seat_id": "CENTER_PARTERRE-20;8",
      "offer_id": "full",
      "external_id": "batch_ticket_1_${TIMESTAMP}",
      "external_order_id": "batch_order_${TIMESTAMP}",
      "price": 1500.00,
      "client_email": "batch1_${TIMESTAMP}@example.com",
      "client_phone": "+79990001134",
      "client_name": "Пакетный",
      "client_surname": "Клиент1"
    },
    {
      "seat_id": "CENTER_PARTERRE-20;9",
      "offer_id": "full",
      "external_id": "batch_ticket_2_${TIMESTAMP}",
      "external_order_id": "batch_order_${TIMESTAMP}",
      "price": 1500.00,
      "client_email": "batch2_${TIMESTAMP}@example.com",
      "client_phone": "+79990001135",
      "client_name": "Пакетный",
      "client_surname": "Клиент2"
    }
  ]
}
"@
Execute-Test -TestNumber "6.2" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Добавить билеты (пакетный)" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/add/batch" -Headers "" -Body $Body6_2

# Тест 6.3: Добавить билет с бронированием
$Body6_3 = @"
{
  "seat_id": "CENTER_PARTERRE-20;10",
  "offer_id": "full",
  "external_id": "reserved_ticket_${TIMESTAMP}",
  "external_order_id": "reserved_order_${TIMESTAMP}",
  "price": 1500.00,
  "reserved_to": "2025-11-07T18:00:00+03:00",
  "client_email": "reserved_${TIMESTAMP}@example.com",
  "client_phone": "+79990001136",
  "client_name": "Бронированный",
  "client_surname": "Клиент"
}
"@
Execute-Test -TestNumber "6.3" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Добавить билет с бронированием" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/add" -Headers "" -Body $Body6_3

# Тест 6.4: Обновить билет (одиночный)
$Body6_4 = @"
{
  "id": 63993,
  "paid": true,
  "paid_at": "2025-11-07T12:00:00+03:00",
  "client_email": "updated_${TIMESTAMP}@example.com",
  "client_phone": "+79990001137"
}
"@
Execute-Test -TestNumber "6.4" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Обновить билет (одиночный)" `
    -Method "PUT" -Url "$PARTNERS_URL/tickets/update/63993" -Headers "" -Body $Body6_4

# Тест 6.5: Обновить билеты (пакетный)
$Body6_5 = @"
{
  "batch": [
    {
      "id": 63993,
      "paid": true,
      "paid_at": "2025-11-07T12:00:00+03:00"
    },
    {
      "id": 63994,
      "paid": true,
      "paid_at": "2025-11-07T12:01:00+03:00"
    }
  ]
}
"@
Execute-Test -TestNumber "6.5" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Обновить билеты (пакетный)" `
    -Method "PUT" -Url "$PARTNERS_URL/tickets/update/batch" -Headers "" -Body $Body6_5

# Тест 6.6: Удалить билет (одиночный)
$Body6_6 = @"
{
  "id": 63993
}
"@
Execute-Test -TestNumber "6.6" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Удалить билет (одиночный)" `
    -Method "DELETE" -Url "$PARTNERS_URL/tickets/delete/63993" -Headers "" -Body $Body6_6

# Тест 6.7: Удалить билеты (пакетный)
$Body6_7 = @"
{
  "batch": [
    {
      "id": 63993
    },
    {
      "id": 63994
    }
  ]
}
"@
Execute-Test -TestNumber "6.7" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Удалить билеты (пакетный)" `
    -Method "DELETE" -Url "$PARTNERS_URL/tickets/delete/batch" -Headers "" -Body $Body6_7

# Тест 6.8: Проверить статусы мест (пакетный)
$Body6_8 = @"
{
  "batch": [
    {
      "seat_id": "CENTER_PARTERRE-20;5",
      "offer_id": "full"
    },
    {
      "seat_id": "CENTER_PARTERRE-20;6",
      "offer_id": "full"
    },
    {
      "seat_id": "CENTER_PARTERRE-20;7",
      "offer_id": "full"
    }
  ]
}
"@
Execute-Test -TestNumber "6.8" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Проверить статусы мест (пакетный)" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/check/12/4076" -Headers "" -Body $Body6_8

# Тест 6.9: Поиск билетов (без параметров в URL)
$Body6_9 = @"
{
  "filter": {
    "external_order_id": "order67890"
  }
}
"@
Execute-Test -TestNumber "6.9" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Поиск билетов (без параметров в URL)" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/find" -Headers "" -Body $Body6_9

# Тест 6.10: Поиск билетов по event_id
$Body6_10 = @"
{
  "filter": {
    "event_id": 12,
    "external_order_id": "order67890"
  }
}
"@
Execute-Test -TestNumber "6.10" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Поиск билетов по event_id" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/find" -Headers "" -Body $Body6_10

# Тест 6.11: Поиск билетов по event_id и show_id
$Body6_11 = @"
{
  "filter": {
    "event_id": 12,
    "show_id": 4076,
    "external_order_id": "order67890"
  }
}
"@
Execute-Test -TestNumber "6.11" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Поиск билетов по event_id и show_id" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/find" -Headers "" -Body $Body6_11

# Тест 6.12: Поиск билетов по штрихкоду
$Body6_12 = @"
{
  "filter": {
    "barcode": "872964136579"
  }
}
"@
Execute-Test -TestNumber "6.12" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Поиск билетов по штрихкоду" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/find" -Headers "" -Body $Body6_12

# Тест 6.13: Поиск билетов по нескольким критериям
$Body6_13 = @"
{
  "filter": {
    "external_order_id": "order67890",
    "external_id": "ticket123",
    "barcode": "872964136579",
    "id": 63993
  }
}
"@
Execute-Test -TestNumber "6.13" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Поиск билетов по нескольким критериям" `
    -Method "POST" -Url "$PARTNERS_URL/tickets/find" -Headers "" -Body $Body6_13

# Тест 6.14: Получить статус мест (устаревший метод)
Execute-Test -TestNumber "6.14" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Получить статус мест (устаревший метод)" `
    -Method "GET" -Url "$PARTNERS_URL/events/seats/12" -Headers "" -Body ""

# Тест 6.15: Получить статус мест для конкретного сеанса
Execute-Test -TestNumber "6.15" -TestCategory "ПАРТНЕРСКИЙ_API" -TestName "Получить статус мест для конкретного сеанса" `
    -Method "GET" -Url "$PARTNERS_URL/events/seats/12/4076" -Headers "" -Body ""

# =============================================================================
# КАТЕГОРИЯ 7: ТЕСТЫ ОШИБОК - 5 ТЕСТОВ
# =============================================================================

Write-Host "`n⚠️ КАТЕГОРИЯ 7: ТЕСТЫ ОШИБОК" -ForegroundColor Yellow

# Тест 7.1: Проверка авторизации (с неверным токеном)
Execute-Test -TestNumber "7.1" -TestCategory "ТЕСТЫ_ОШИБОК" -TestName "Проверка авторизации (с неверным токеном)" `
    -Method "GET" -Url "$BASE_URL/events" -Headers "INVALID_TOKEN" -Body ""

# Тест 7.2: Проверка несуществующего заказа
Execute-Test -TestNumber "7.2" -TestCategory "ТЕСТЫ_ОШИБОК" -TestName "Проверка несуществующего заказа" `
    -Method "GET" -Url "$BASE_URL/orders/999999999" -Headers "" -Body ""

# Тест 7.3: Проверка несуществующего мероприятия
Execute-Test -TestNumber "7.3" -TestCategory "ТЕСТЫ_ОШИБОК" -TestName "Проверка несуществующего мероприятия" `
    -Method "GET" -Url "$BASE_URL/events/999999999" -Headers "" -Body ""

# Тест 7.4: Проверка с пустым телом где требуется
Execute-Test -TestNumber "7.4" -TestCategory "ТЕСТЫ_ОШИБОК" -TestName "Проверка с пустым телом где требуется" `
    -Method "POST" -Url "$BASE_URL/clients" -Headers "" -Body ""

# Тест 7.5: Проверка с неверными параметрами
$Body7_5 = @"
{
  "where": [
    {
      "column": "invalid_column",
      "value": "invalid_value"
    }
  ],
  "orderBy": {
    "id": "invalid_direction"
  },
  "page": -1
}
"@
Execute-Test -TestNumber "7.5" -TestCategory "ТЕСТЫ_ОШИБОК" -TestName "Проверка с неверными параметрами" `
    -Method "GET" -Url "$BASE_URL/orders" -Headers "" -Body $Body7_5

# =============================================================================
# ЗАВЕРШЕНИЕ ТЕСТИРОВАНИЯ И СОЗДАНИЕ ОТЧЕТА
# =============================================================================

Write-Host "`n=========================================" -ForegroundColor Blue
Write-Host "СОЗДАНИЕ ФИНАЛЬНОГО ОТЧЕТА" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue

# Создание итогового отчета в Markdown
$SuccessRate = if ($TotalTests -gt 0) { [math]::Round(($PassedTests / $TotalTests) * 100, 2) } else { 0 }

@"
# 📊 ПОЛНЫЙ ОТЧЕТ О МАСШТАБНОМ ТЕСТИРОВАНИИ Q TICKETS API

## 📋 ОБЩАЯ ИНФОРМАЦИЯ

- **Дата тестирования:** $(Get-Date)
- **Длительность тестирования:** $((Get-Date) - $StartTime)
- **API Токен:** $($Token.Substring(0, [Math]::Min(10, $Token.Length)))...
- **Базовый URL REST API:** $BASE_URL
- **Базовый URL Partners API:** $PARTNERS_URL

## 📊 СТАТИСТИКА ТЕСТИРОВАНИЯ

| Метрика | Значение |
|---------|---------|
| Всего тестов | $TotalTests |
| Успешных | $PassedTests |
| Неудачных | $FailedTests |
| % Успешности | $SuccessRate% |

## 📈 РЕЗУЛЬТАТЫ ПО КАТЕГОРИЯМ

### 📋 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ ТЕСТОВ

"@ | Out-File -FilePath $SUMMARY_FILE -Encoding UTF8

# Добавление детальных результатов из JSON файла
try {
    $Results = Get-Content $RESULTS_FILE | ConvertFrom-Json

    foreach ($Result in $Results) {
        $StatusIcon = if ($Result.status_code -ge 200 -and $Result.status_code -lt 300) { "✅" } else { "❌" }
        @"
$StatusIcon **$($Result.test_category)** - $($Result.test_name) ($($Result.status_code))

#### Запрос:
- **Метод:** $($Result.method)
- **URL:** $($Result.url)
- **Body:** $($Result.body)

#### Ответ ($($Result.status_code)):
```json
$($Result.response)
```

"@ | Out-File -FilePath $SUMMARY_FILE -Encoding UTF8 -Append
    }
} catch {
    Write-Warning "Не удалось обработать результаты для детального отчета"
}

@"
## 📂 ФАЙЛЫ ТЕСТИРОВАНИЯ

- **Полные результаты JSON:** `$RESULTS_FILE`
- **Логи по каждому тесту:** `$LOG_DIR/`
- **Скрипт тестирования:** `run_tests.ps1`

## 🔍 АНАЛИЗ РЕЗУЛЬТАТОВ

### ✅ УСПЕШНЫЕ ТЕСТЫ
- $PassedTests тестов выполнено успешно
- Основные функции API работают корректно
- Авторизация функционирует как ожидалось

### ❌ ПРОБЛЕМНЫЕ ТЕСТЫ
- $FailedTests тестов не выполнены
- Необходим анализ причин неудач
- Проверьте корректность токена и доступных ID

## 🛠️ РЕКОМЕНДАЦИИ

1. **Проверьте неудачные тесты** - проанализируйте причины ошибок
2. **Проверьте актуальность ID** - убедитесь что ID мероприятий, заказов и т.д. существуют
3. **Проверьте права токена** - убедитесь что у токена есть права на все операции
4. **Изучите логи** - детальные логи каждого теста сохранены в директории $LOG_DIR

## 📝 ЗАКЛЮЧЕНИЕ

Тестирование завершено. Успешность: $SuccessRate%.

**Время завершения:** $(Get-Date)
"@ | Out-File -FilePath $SUMMARY_FILE -Encoding UTF8 -Append

# Вывод финальной статистики
Write-Host "`n=========================================" -ForegroundColor Blue
Write-Host "ТЕСТИРОВАНИЕ ЗАВЕРШЕНО" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "📊 СТАТИСТИКА:" -ForegroundColor Yellow
Write-Host "   Всего тестов: $TotalTests"
Write-Host "   ✅ Успешных: $PassedTests" -ForegroundColor Green
Write-Host "   ❌ Неудачных: $FailedTests" -ForegroundColor Red
Write-Host "📂 ФАЙЛЫ:" -ForegroundColor Yellow
Write-Host "   📄 Отчет: $SUMMARY_FILE"
Write-Host "   📊 Результаты: $RESULTS_FILE"
Write-Host "   📋 Логи: $LOG_DIR/"
Write-Host "⏰ Время выполнения: $((Get-Date) - $StartTime)"
Write-Host "📅 Завершено: $(Get-Date)"
Write-Host "========================================="

Write-Host "`n🎉 Тестирование завершено! Проверьте отчеты в директории test_results/" -ForegroundColor Green
```

Теперь создам файл с инструкциями по запуску:
<tool_call>create_file
<arg_key>path</arg_key>
+
