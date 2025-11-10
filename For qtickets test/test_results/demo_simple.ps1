# =============================================================================
# Qtickets API - ДЕМОНСТРАЦИОННЫЙ ЗАПУСК (с мок данными)
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
Write-Host "Qtickets API - DEMONSTRATION RUN" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Start time: $(Get-Date)"
Write-Host "Mode: Demo with mock data"
Write-Host "========================================="

# Mock data for demonstration
$MockResponses = @{
    "1.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 4360; payed = 1; total = 1500.00 }); pagination = @{ current_page = 1; total = 1; per_page = 20 } } }
    "1.2" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 4360; payed = 1; status = "paid" }); filters = @{ where = @(@{ column = "payed"; value = 1 }) } } }
    "1.6" = @{ status = 200; data = @{ status = "success"; data = @{ id = 4360; payed = 1; total = 1500.00; client = @{ id = 235; name = "Ivan"; surname = "Ivanov" } } } }
    "2.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 235; name = "Ivan"; surname = "Ivanov"; email = "ivan@example.com" }) } }
    "2.3" = @{ status = 201; data = @{ status = "success"; data = @{ id = 236; email = "test_client@example.com"; name = "Test"; surname = "Client" } } }
    "3.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 12; name = "Symphony Orchestra Concert" }, @{ id = 33; name = "Theatrical Performance" }) } }
    "3.3" = @{ status = 200; data = @{ status = "success"; data = @{ id = 33; name = "Theatrical Performance"; description = "Modern drama"; start_date = "2025-11-20T18:30:00+03:00" } } }
    "4.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 1; name = "Standard"; color = "#000000" }, @{ id = 2; name = "VIP"; color = "#FFD700" }) } }
    "5.1" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63993; barcode = "872964136579"; order_id = 4360; scanned = $false }) } }
    "6.1" = @{ status = 201; data = @{ status = "success"; data = @{ id = 63995; external_id = "test_ticket_20251107"; barcode = "872964136581" } } }
    "6.8" = @{ status = 200; data = @{ status = "success"; data = @(@{ seat_id = "CENTER_PARTERRE-20;5"; available = $false; status = "sold" }, @{ seat_id = "CENTER_PARTERRE-20;6"; available = $true; status = "available" }) } }
    "6.12" = @{ status = 200; data = @{ status = "success"; data = @(@{ id = 63993; barcode = "872964136579" }) } }
    "7.1" = @{ status = 401; data = @{ status = "error"; error = "WRONG_AUTHORIZATION"; message = "Invalid authorization token" } }
    "7.2" = @{ status = 404; data = @{ status = "error"; error = "ORDER_NOT_FOUND"; message = "Order not found" } }
    "7.4" = @{ status = 400; data = @{ status = "error"; error = "VALIDATION_ERROR"; message = "Data validation error" } }
}

# Test scenarios for demonstration
$TestScenarios = @(
    @{ Number = "1.1"; Category = "ORDERS"; Name = "Get all orders list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders" }
    @{ Number = "1.2"; Category = "ORDERS"; Name = "Get paid orders list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders" }
    @{ Number = "1.6"; Category = "ORDERS"; Name = "Get specific order #4360"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders/4360" }
    @{ Number = "2.1"; Category = "CLIENTS"; Name = "Get clients list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/clients" }
    @{ Number = "2.3"; Category = "CLIENTS"; Name = "Create client"; Method = "POST"; URL = "https://qtickets.ru/api/rest/v1/clients" }
    @{ Number = "3.1"; Category = "EVENTS"; Name = "Get events list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events" }
    @{ Number = "3.3"; Category = "EVENTS"; Name = "Get specific event #33"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events/33" }
    @{ Number = "4.1"; Category = "DISCOUNTS"; Name = "Get price colors list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/discounts/colors" }
    @{ Number = "5.1"; Category = "BARCODES"; Name = "Get tickets barcodes list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/barcodes" }
    @{ Number = "6.1"; Category = "PARTNERS_API"; Name = "Add ticket (single)"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/add" }
    @{ Number = "6.8"; Category = "PARTNERS_API"; Name = "Check seats status (batch)"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/check/12/4076" }
    @{ Number = "6.12"; Category = "PARTNERS_API"; Name = "Find tickets by barcode"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/find" }
    @{ Number = "7.1"; Category = "ERROR_TESTS"; Name = "Authorization check (invalid token)"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events" }
    @{ Number = "7.2"; Category = "ERROR_TESTS"; Name = "Check non-existent order"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders/999999999" }
    @{ Number = "7.4"; Category = "ERROR_TESTS"; Name = "Check with empty body where required"; Method = "POST"; URL = "https://qtickets.ru/api/rest/v1/clients" }
)

# Initialize JSON results file
"[" | Out-File -FilePath $RESULTS_FILE -Encoding UTF8

# Execute demonstration tests
foreach ($Test in $TestScenarios) {
    $TotalTests++

    Write-Host "`n🔍 Executing: $($Test.Name)" -ForegroundColor Yellow
    Start-Sleep -Milliseconds 300  # Network delay simulation

    $MockResponse = $MockResponses[$Test.Number]
    $StatusCode = $MockResponse.status
    $ResponseData = $MockResponse.data | ConvertTo-Json -Depth 10 -Compress

    # Logging
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

    # Save to file (add comma if not first)
    if ($TotalTests -gt 1) {
        Add-Content -Path $RESULTS_FILE -Value ","
    }
    Add-Content -Path $RESULTS_FILE -Value $LogEntry

    # Display result
    if ($StatusCode -ge 200 -and $StatusCode -lt 300) {
        Write-Host "✅ Test $($Test.Number): $($Test.Name) ($StatusCode)" -ForegroundColor Green
        $PassedTests++
    } else {
        Write-Host "❌ Test $($Test.Number): $($Test.Name) ($StatusCode)" -ForegroundColor Red
        $FailedTests++
    }

    # Detailed log
    $LogFileName = "test_$($Test.Number -replace '\.', '_')_$($Test.Name -replace ' ', '_').log"
    $LogPath = Join-Path $LOG_DIR $LogFileName

    @"
========================================
TEST $($Test.Number): $($Test.Name)
Category: $($Test.Category)
Method: $($Test.Method)
URL: $($Test.URL)
Headers: {"Authorization": "Bearer DEMO_TOKEN_***"}
Body: $(if ($Test.Method -eq "POST") { '{"demo": "data"}' } else { '' })
Status Code: $StatusCode
Response:
$ResponseData
========================================
"@ | Out-File -FilePath $LogPath -Encoding UTF8
}

# Close JSON array
"]" | Out-File -FilePath $RESULTS_FILE -Encoding UTF8 -Append

# Create report
$SuccessRate = if ($TotalTests -gt 0) { [math]::Round(($PassedTests / $TotalTests) * 100, 2) } else { 0 }

$Report = @"
# 📊 DEMONSTRATION REPORT FOR Q TICKETS API TESTING

## 📋 GENERAL INFORMATION

- **Test Date:** $(Get-Date)
- **Mode:** Demo with mock data
- **Purpose:** Show testing system functionality
- **API Token:** DEMO_TOKEN_***

## 📊 TESTING STATISTICS

| Metric | Value |
|---------|---------|
| Total Tests | $TotalTests |
| Successful | $PassedTests |
| Failed | $FailedTests |
| Success Rate | $SuccessRate% |

## 📈 RESULTS BY CATEGORIES

### 🎪 ORDERS
✅ Test 1.1: Get all orders list (200)
✅ Test 1.2: Get paid orders list (200)
✅ Test 1.6: Get specific order #4360 (200)

### 👥 CLIENTS
✅ Test 2.1: Get clients list (200)
✅ Test 2.3: Create client (201)

### 🎭 EVENTS
✅ Test 3.1: Get events list (200)
✅ Test 3.3: Get specific event #33 (200)

### 🎫 DISCOUNTS
✅ Test 4.1: Get price colors list (200)

### 📊 BARCODES
✅ Test 5.1: Get tickets barcodes list (200)

### 🤝 PARTNERS API
✅ Test 6.1: Add ticket (single) (201)
✅ Test 6.8: Check seats status (batch) (200)
✅ Test 6.12: Find tickets by barcode (200)

### ⚠️ ERROR TESTS
❌ Test 7.1: Authorization check (invalid token) (401)
❌ Test 7.2: Check non-existent order (404)
❌ Test 7.4: Check with empty body where required (400)

## 📋 DETAILED RESPONSE EXAMPLES

### ✅ Successful Response (GET /orders)
\`\`\`json
$($MockResponses["1.1"].data | ConvertTo-Json -Depth 10)
\`\`\`

### ✅ Successful Response (POST /clients)
\`\`\`json
$($MockResponses["2.3"].data | ConvertTo-Json -Depth 10)
\`\`\`

### ❌ Error Response (GET /events with invalid token)
\`\`\`json
$($MockResponses["7.1"].data | ConvertTo-Json -Depth 10)
\`\`\`

## 📂 TESTING FILES

- **Full results:** \`$RESULTS_FILE\`
- **Test logs:** \`$LOG_DIR/\`

## 🛠️ NEXT STEPS

1. **Get real API token** from Qtickets personal cabinet
2. **Run full test:** \`.\run_tests.ps1 YOUR_API_TOKEN\`
3. **Study real API responses**
4. **Adapt IDs** for your system

## 📝 CONCLUSION

Demonstration completed successfully! System is ready for full testing.

**For real testing use:** \`.\run_tests.ps1 YOUR_API_TOKEN\`

**Completion time:** $(Get-Date)
"@

$Report | Out-File -FilePath $SUMMARY_FILE -Encoding UTF8

# Final statistics
Write-Host "`n=========================================" -ForegroundColor Blue
Write-Host "DEMONSTRATION COMPLETED" -ForegroundColor Blue
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
Write-Host "🎉 Demo run completed!" -ForegroundColor Green
Write-Host "📝 View report: $SUMMARY_FILE" -ForegroundColor Cyan
Write-Host "🚀 For real testing: .\run_tests.ps1 YOUR_API_TOKEN" -ForegroundColor Yellow
Write-Host "========================================="
