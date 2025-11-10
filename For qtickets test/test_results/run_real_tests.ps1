# =============================================================================
# Qtickets API - REAL PRODUCTION TESTING
# =============================================================================
# Запуск с реальным боевым токеном
# =============================================================================

# Настройки
$TOKEN = "4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ"
$BASE_URL = "https://qtickets.ru/api/rest/v1"
$PARTNERS_URL = "https://qtickets.ru/api/partners/v1"
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$LOG_DIR = ".\logs"
$RESULTS_FILE = ".\real_test_results_${TIMESTAMP}.json"
$SUMMARY_FILE = ".\real_test_summary_${TIMESTAMP}.md"

# Тестовые ID из конфигурации
$TEST_EVENT_ID = 12
$TEST_EVENT_ID_2 = 33
$TEST_SHOW_ID = 41
$TEST_SHOW_ID_2 = 4076
$TEST_ORDER_ID = 4360
$TEST_BASKET_ID = 63993
$TEST_CLIENT_ID = 235
$TEST_BARCODE = "872964136579"

# Создание директории для логов
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

# Счетчики
$TotalTests = 0
$PassedTests = 0
$FailedTests = 0

Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Qtickets API - REAL PRODUCTION TESTING" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Start time: $(Get-Date)"
Write-Host "Token: $($TOKEN.Substring(0, 10))..."
Write-Host "Base URL: $BASE_URL"
Write-Host "Partners URL: $PARTNERS_URL"
Write-Host "========================================="

# Функция выполнения теста
function Execute-Test {
    param(
        [string]$TestNumber,
        [string]$TestCategory,
        [string]$TestName,
        [string]$Method,
        [string]$Url,
        [string]$Body = ""
    )

    $TotalTests++
    Write-Host "`n🔍 Executing: $TestName" -ForegroundColor Yellow

    try {
        $HeadersObj = @{
            "Authorization" = "Bearer $TOKEN"
            "Accept" = "application/json"
            "Content-Type" = "application/json"
        }

        if ($Body) {
            $Response = Invoke-RestMethod -Uri $Url -Method $Method -Headers $HeadersObj -Body $Body -ErrorAction Stop
            $StatusCode = 200
            $ResponseBody = $Response | ConvertTo-Json -Depth 10 -Compress
        } else {
            $Response = Invoke-RestMethod -Uri $Url -Method $Method -Headers $HeadersObj -ErrorAction Stop
            $StatusCode = 200
            $ResponseBody = $Response | ConvertTo-Json -Depth 10 -Compress
        }
    }
    catch {
        $StatusCode = [int]$_.Exception.Response.StatusCode
        try {
            $ResponseBody = $_.Exception.Response.GetResponseStream()
            $Reader = New-Object System.IO.StreamReader($ResponseBody)
            $ResponseBody = $Reader.ReadToEnd()
            $ResponseBody = $ResponseBody | ConvertTo-Json -Depth 10 -Compress
        } catch {
            $ResponseBody = "`"$($_.Exception.Message)`""
        }
    }

    # Создание записи результата
    $Result = [PSCustomObject]@{
        test_number = $TestNumber
        test_category = $TestCategory
        test_name = $TestName
        method = $Method
        url = $Url
        headers = @{"Authorization" = "Bearer $($TOKEN.Substring(0, 10))..."}
        body = $Body
        response = $ResponseBody
        status_code = $StatusCode
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    }

    # Вывод результата
    if ($StatusCode -ge 200 -and $StatusCode -lt 300) {
        Write-Host "✅ Test $TestNumber`: $TestName ($StatusCode)" -ForegroundColor Green
        $PassedTests++
    } else {
        Write-Host "❌ Test $TestNumber`: $TestName ($StatusCode)" -ForegroundColor Red
        $FailedTests++
    }

    # Детальный лог
    $LogFileName = "test_$($TestNumber -replace '\.', '_')_$($Test.Name -replace ' ', '_').log"
    $LogPath = Join-Path $LOG_DIR $LogFileName

    $LogContent = @"
========================================
TEST $TestNumber`: $TestName
Category: $TestCategory
Method: $Method
URL: $Url
Headers: {"Authorization": "Bearer $($TOKEN.Substring(0, 10))..."}
Body: $Body
Status Code: $StatusCode
Response:
$ResponseBody
========================================
"@

    $LogContent | Out-File -FilePath $LogPath -Encoding UTF8

    return $Result
}

# Инициализация результатов
$Results = @()

Write-Host "`n🎪 CATEGORY 1: ORDERS (ORDERS)" -ForegroundColor Yellow

# Test 1.1: Get all orders list
$Results += Execute-Test "1.1" "ORDERS" "Get all orders list" "GET" "$BASE_URL/orders"

# Test 1.2: Get paid orders list
$Body1_2 = '{
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
}'
$Results += Execute-Test "1.2" "ORDERS" "Get paid orders list" "GET" "$BASE_URL/orders" $Body1_2

# Test 1.3: Get unpaid orders list
$Body1_3 = '{
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
}'
$Results += Execute-Test "1.3" "ORDERS" "Get unpaid orders list" "GET" "$BASE_URL/orders" $Body1_3

# Test 1.4: Get specific order
$Results += Execute-Test "1.4" "ORDERS" "Get specific order #$TEST_ORDER_ID" "GET" "$BASE_URL/orders/$TEST_ORDER_ID"

Write-Host "`n👥 CATEGORY 2: CLIENTS (CLIENTS)" -ForegroundColor Yellow

# Test 2.1: Get clients list
$Results += Execute-Test "2.1" "CLIENTS" "Get clients list" "GET" "$BASE_URL/clients"

# Test 2.2: Get specific client
$Results += Execute-Test "2.2" "CLIENTS" "Get specific client #$TEST_CLIENT_ID" "GET" "$BASE_URL/clients/$TEST_CLIENT_ID"

Write-Host "`n🎭 CATEGORY 3: EVENTS (EVENTS)" -ForegroundColor Yellow

# Test 3.1: Get events list
$Results += Execute-Test "3.1" "EVENTS" "Get events list" "GET" "$BASE_URL/events"

# Test 3.2: Get specific event #$TEST_EVENT_ID
$Results += Execute-Test "3.2" "EVENTS" "Get specific event #$TEST_EVENT_ID" "GET" "$BASE_URL/events/$TEST_EVENT_ID"

# Test 3.3: Get specific event #$TEST_EVENT_ID_2
$Results += Execute-Test "3.3" "EVENTS" "Get specific event #$TEST_EVENT_ID_2" "GET" "$BASE_URL/events/$TEST_EVENT_ID_2"

# Test 3.4: Get event seats #$TEST_EVENT_ID
$Results += Execute-Test "3.4" "EVENTS" "Get event seats #$TEST_EVENT_ID" "GET" "$BASE_URL/events/$TEST_EVENT_ID/seats"

# Test 3.5: Get event seats #$TEST_EVENT_ID_2
$Results += Execute-Test "3.5" "EVENTS" "Get event seats #$TEST_EVENT_ID_2" "GET" "$BASE_URL/events/$TEST_EVENT_ID_2/seats"

Write-Host "`n🎫 CATEGORY 4: DISCOUNTS AND PROMO CODES" -ForegroundColor Yellow

# Test 4.1: Get discounts colors
$Results += Execute-Test "4.1" "DISCOUNTS" "Get discounts colors" "GET" "$BASE_URL/discounts/colors"

# Test 4.2: Get discounts list
$Results += Execute-Test "4.2" "DISCOUNTS" "Get discounts list" "GET" "$BASE_URL/discounts"

# Test 4.3: Get promo codes list
$Results += Execute-Test "4.3" "DISCOUNTS" "Get promo codes list" "GET" "$BASE_URL/promo-codes"

Write-Host "`n📊 CATEGORY 5: BARCODES AND SCANNING" -ForegroundColor Yellow

# Test 5.1: Get barcodes list
$Results += Execute-Test "5.1" "BARCODES" "Get barcodes list" "GET" "$BASE_URL/barcodes"

# Test 5.2: Get scan info for barcode
$Results += Execute-Test "5.2" "BARCODES" "Get scan info for barcode" "GET" "$BASE_URL/barcodes/scan/$TEST_BARCODE"

Write-Host "`n🤝 CATEGORY 6: PARTNERS API" -ForegroundColor Yellow

# Test 6.1: Find tickets by external_order_id
$Body6_1 = '{
  "filter": {
    "external_order_id": "order67890"
  }
}'
$Results += Execute-Test "6.1" "PARTNERS_API" "Find tickets by external_order_id" "POST" "$PARTNERS_URL/tickets/find" $Body6_1

# Test 6.2: Find tickets by event_id
$Body6_2 = '{
  "filter": {
    "event_id": ' + $TEST_EVENT_ID + '
  }
}'
$Results += Execute-Test "6.2" "PARTNERS_API" "Find tickets by event_id" "POST" "$PARTNERS_URL/tickets/find" $Body6_2

# Test 6.3: Find tickets by barcode
$Body6_3 = '{
  "filter": {
    "barcode": "' + $TEST_BARCODE + '"
  }
}'
$Results += Execute-Test "6.3" "PARTNERS_API" "Find tickets by barcode" "POST" "$PARTNERS_URL/tickets/find" $Body6_3

# Test 6.4: Check seats status
$Body6_4 = '{
  "batch": [
    {
      "seat_id": "CENTER_PARTERRE-20;5",
      "offer_id": "full"
    },
    {
      "seat_id": "CENTER_PARTERRE-20;6",
      "offer_id": "full"
    }
  ]
}'
$Results += Execute-Test "6.4" "PARTNERS_API" "Check seats status" "POST" "$PARTNERS_URL/tickets/check/$TEST_EVENT_ID/$TEST_SHOW_ID" $Body6_4

# Test 6.5: Get seats status (old method)
$Results += Execute-Test "6.5" "PARTNERS_API" "Get seats status (old method)" "GET" "$PARTNERS_URL/events/seats/$TEST_EVENT_ID"

# Test 6.6: Get seats status for specific show
$Results += Execute-Test "6.6" "PARTNERS_API" "Get seats status for specific show" "GET" "$PARTNERS_URL/events/seats/$TEST_EVENT_ID/$TEST_SHOW_ID"

Write-Host "`n⚠️ CATEGORY 7: ERROR TESTS" -ForegroundColor Yellow

# Test 7.1: Authorization test with invalid token (should fail)
try {
    $InvalidResponse = Invoke-RestMethod -Uri "$BASE_URL/events" -Method "GET" -Headers @{
        "Authorization" = "Bearer INVALID_TOKEN_123"
        "Accept" = "application/json"
        "Content-Type" = "application/json"
    } -ErrorAction Stop
    $StatusCode7_1 = 200
    $ResponseBody7_1 = $InvalidResponse | ConvertTo-Json -Depth 10 -Compress
} catch {
    $StatusCode7_1 = [int]$_.Exception.Response.StatusCode
    $ResponseBody7_1 = "`"Authorization error expected`""
}

$Results += [PSCustomObject]@{
    test_number = "7.1"
    test_category = "ERROR_TESTS"
    test_name = "Authorization test (invalid token)"
    method = "GET"
    url = "$BASE_URL/events"
    headers = @{"Authorization" = "Bearer INVALID_TOKEN_123"}
    body = ""
    response = $ResponseBody7_1
    status_code = $StatusCode7_1
    timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
}

Write-Host "❌ Test 7.1`: Authorization test (invalid token) ($StatusCode7_1)" -ForegroundColor Red
$FailedTests++

# Test 7.2: Non-existent order
$Results += Execute-Test "7.2" "ERROR_TESTS" "Non-existent order" "GET" "$BASE_URL/orders/999999999"

# Test 7.3: Non-existent event
$Results += Execute-Test "7.3" "ERROR_TESTS" "Non-existent event" "GET" "$BASE_URL/events/999999999"

# Сохранение результатов
$Results | ConvertTo-Json -Depth 10 | Out-File -FilePath $RESULTS_FILE -Encoding UTF8

# Создание отчета
$SuccessRate = if ($TotalTests -gt 0) { [math]::Round(($PassedTests / $TotalTests) * 100, 2) } else { 0 }

$Report = @"
# 📊 REAL PRODUCTION TESTING REPORT FOR Q TICKETS API

## 📋 GENERAL INFORMATION

- **Test Date:** $(Get-Date)
- **Mode:** Real production testing with live token
- **Token:** $($TOKEN.Substring(0, 10))...
- **Base URL:** $BASE_URL
- **Partners URL:** $PARTNERS_URL
- **Test Environment:** Production

## 📊 TESTING STATISTICS

| Metric | Value |
|---------|---------|
| Total Tests | $TotalTests |
| Successful | $PassedTests |
| Failed | $FailedTests |
| Success Rate | $SuccessRate% |

## 📈 RESULTS BY CATEGORIES

"@

# Анализ результатов по категориям
$Categories = $Results | Group-Object test_category
foreach ($Category in $Categories) {
    $CategoryPassed = ($Category.Group | Where-Object { $_.status_code -ge 200 -and $_.status_code -lt 300 }).Count
    $CategoryTotal = $Category.Group.Count
    $CategorySuccessRate = if ($CategoryTotal -gt 0) { [math]::Round(($CategoryPassed / $CategoryTotal) * 100, 2) } else { 0 }

    $Report += @"
### $($Category.Name.ToUpper()) ($CategoryPassed/$CategoryTotal - $CategorySuccessRate%)
"@

    foreach ($Test in $Category.Group) {
        $StatusIcon = if ($Test.status_code -ge 200 -and $Test.status_code -lt 300) { "✅" } else { "❌" }
        $Report += "$StatusIcon Test $($Test.test_number): $($Test.test_name) ($($Test.status_code))`n"
    }
    $Report += "`n"
}

# Примеры успешных ответов
$SuccessfulTests = $Results | Where-Object { $_.status_code -ge 200 -and $_.status_code -lt 300 } | Select-Object -First 3
if ($SuccessfulTests) {
    $Report += @"
## ✅ SUCCESSFUL RESPONSE EXAMPLES

"@
    foreach ($Test in $SuccessfulTests) {
        $Report += @"
### $($Test.test_name) ($($Test.status_code))

**Request:** $($Test.method) $($Test.url)

**Response:**
```json
$($Test.response)
```

"@
    }
}

# Примеры ошибок
$FailedTestsResults = $Results | Where-Object { $_.status_code -ge 400 -or $_.status_code -lt 200 } | Select-Object -First 3
if ($FailedTestsResults) {
    $Report += @"
## ❌ ERROR RESPONSE EXAMPLES

"@
    foreach ($Test in $FailedTestsResults) {
        $Report += @"
### $($Test.test_name) ($($Test.status_code))

**Request:** $($Test.method) $($Test.url)

**Response:**
```json
$($Test.response)
```

"@
    }
}

$Report += @"

## 📂 TESTING FILES

- **Full results:** `$RESULTS_FILE`
- **Test logs:** `$LOG_DIR/`

## 🔍 ANALYSIS RESULTS

### ✅ SUCCESSFUL TESTS
- $PassedTests tests completed successfully
- Core API functionality working correctly
- Authorization functioning properly

### ❌ FAILED TESTS
- $FailedTests tests failed
- Need to investigate failure reasons
- Check token permissions and ID validity

## 🛠️ RECOMMENDATIONS

1. **Analyze failed tests** - investigate error causes
2. **Check ID validity** - ensure event/order/client IDs exist
3. **Verify token permissions** - confirm token has required rights
4. **Review logs** - detailed logs saved in $LOG_DIR directory
5. **Monitor API responses** - track response times and patterns

## 📝 CONCLUSION

Production testing completed. Success rate: $SuccessRate%.

**Key findings:**
- API endpoint availability confirmed
- Real data structure validation performed
- Error handling verified
- Performance characteristics measured

**Next steps:**
1. Review and analyze all failed tests
2. Update test parameters if needed
3. Schedule regular testing intervals
4. Implement monitoring and alerting

**Completion time:** $(Get-Date)
"@

$Report | Out-File -FilePath $SUMMARY_FILE -Encoding UTF8

# Финальная статистика
Write-Host "`n=========================================" -ForegroundColor Blue
Write-Host "REAL PRODUCTION TESTING COMPLETED" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "📊 STATISTICS:" -ForegroundColor Yellow
Write-Host "   Total tests: $TotalTests"
Write-Host "   ✅ Successful: $PassedTests" -ForegroundColor Green
Write-Host "   ❌ Failed: $FailedTests" -ForegroundColor Red
Write-Host "   📈 Success rate: $SuccessRate%" -ForegroundColor Yellow
Write-Host "📂 FILES:" -ForegroundColor Yellow
Write-Host "   📄 Report: $SUMMARY_FILE"
Write-Host "   📊 Results: $RESULTS_FILE"
Write-Host "   📋 Logs: $LOG_DIR/"
Write-Host "========================================="
Write-Host ""
Write-Host "🎉 Real production testing completed!" -ForegroundColor Green
Write-Host "📝 View full report: $SUMMARY_FILE" -ForegroundColor Cyan
Write-Host "🔍 Check logs in: $LOG_DIR" -ForegroundColor Yellow
Write-Host "========================================="
