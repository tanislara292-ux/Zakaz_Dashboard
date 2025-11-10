# =============================================================================
# Qtickets API - DEMONSTRATION RUN (Basic Version)
# =============================================================================

# Settings
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$LOG_DIR = ".\logs"
$RESULTS_FILE = ".\demo_test_results_${TIMESTAMP}.json"
$SUMMARY_FILE = ".\demo_test_summary_${TIMESTAMP}.md"

# Create logs directory
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

# Counters
$TotalTests = 0
$PassedTests = 0
$FailedTests = 0

Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Qtickets API - DEMONSTRATION RUN" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "Start time: $(Get-Date)"
Write-Host "Mode: Demo with mock data"
Write-Host "========================================="

# Test scenarios
$Tests = @(
    @{ Number = "1.1"; Category = "ORDERS"; Name = "Get all orders list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders"; Status = 200 }
    @{ Number = "1.2"; Category = "ORDERS"; Name = "Get paid orders list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders"; Status = 200 }
    @{ Number = "1.6"; Category = "ORDERS"; Name = "Get specific order #4360"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders/4360"; Status = 200 }
    @{ Number = "2.1"; Category = "CLIENTS"; Name = "Get clients list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/clients"; Status = 200 }
    @{ Number = "2.3"; Category = "CLIENTS"; Name = "Create client"; Method = "POST"; URL = "https://qtickets.ru/api/rest/v1/clients"; Status = 201 }
    @{ Number = "3.1"; Category = "EVENTS"; Name = "Get events list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events"; Status = 200 }
    @{ Number = "3.3"; Category = "EVENTS"; Name = "Get specific event #33"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events/33"; Status = 200 }
    @{ Number = "4.1"; Category = "DISCOUNTS"; Name = "Get price colors list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/discounts/colors"; Status = 200 }
    @{ Number = "5.1"; Category = "BARCODES"; Name = "Get tickets barcodes list"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/barcodes"; Status = 200 }
    @{ Number = "6.1"; Category = "PARTNERS_API"; Name = "Add ticket (single)"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/add"; Status = 201 }
    @{ Number = "6.8"; Category = "PARTNERS_API"; Name = "Check seats status (batch)"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/check/12/4076"; Status = 200 }
    @{ Number = "6.12"; Category = "PARTNERS_API"; Name = "Find tickets by barcode"; Method = "POST"; URL = "https://qtickets.ru/api/partners/v1/tickets/find"; Status = 200 }
    @{ Number = "7.1"; Category = "ERROR_TESTS"; Name = "Authorization check (invalid token)"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/events"; Status = 401 }
    @{ Number = "7.2"; Category = "ERROR_TESTS"; Name = "Check non-existent order"; Method = "GET"; URL = "https://qtickets.ru/api/rest/v1/orders/999999999"; Status = 404 }
    @{ Number = "7.4"; Category = "ERROR_TESTS"; Name = "Check with empty body where required"; Method = "POST"; URL = "https://qtickets.ru/api/rest/v1/clients"; Status = 400 }
)

# Initialize results array
$Results = @()

# Execute tests
foreach ($Test in $Tests) {
    $TotalTests++

    Write-Host "`nExecuting: $($Test.Name)" -ForegroundColor Yellow
    Start-Sleep -Milliseconds 300

    # Mock response
    $ResponseBody = if ($Test.Status -ge 200 -and $Test.Status -lt 300) {
        '{"status": "success", "data": {"id": "123", "message": "Demo response"}}'
    } else {
        '{"status": "error", "error": "DEMO_ERROR", "message": "Demo error response"}'
    }

    # Create result object
    $Result = [PSCustomObject]@{
        test_number = $Test.Number
        test_category = $Test.Category
        test_name = $Test.Name
        method = $Test.Method
        url = $Test.URL
        headers = '{"Authorization": "Bearer DEMO_TOKEN_***"}'
        body = if ($Test.Method -eq "POST") { '{"demo": "data"}' } else { '' }
        response = $ResponseBody
        status_code = $Test.Status
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    }

    $Results += $Result

    # Display result
    if ($Test.Status -ge 200 -and $Test.Status -lt 300) {
        Write-Host "Test $($Test.Number): $($Test.Name) ($($Test.Status))" -ForegroundColor Green
        $PassedTests++
    } else {
        Write-Host "Test $($Test.Number): $($Test.Name) ($($Test.Status))" -ForegroundColor Red
        $FailedTests++
    }

    # Save detailed log
    $LogFileName = "test_$($Test.Number -replace '\.', '_')_$($Test.Name -replace ' ', '_').log"
    $LogPath = Join-Path $LOG_DIR $LogFileName

    $LogContent = @"
========================================
TEST $($Test.Number): $($Test.Name)
Category: $($Test.Category)
Method: $($Test.Method)
URL: $($Test.URL)
Headers: {"Authorization": "Bearer DEMO_TOKEN_***"}
Body: $(if ($Test.Method -eq "POST") { '{"demo": "data"}' } else { '' })
Status Code: $($Test.Status)
Response:
$ResponseBody
========================================
"@

    $LogContent | Out-File -FilePath $LogPath -Encoding UTF8
}

# Save results to JSON
$Results | ConvertTo-Json -Depth 10 | Out-File -FilePath $RESULTS_FILE -Encoding UTF8

# Calculate success rate
$SuccessRate = if ($TotalTests -gt 0) { [math]::Round(($PassedTests / $TotalTests) * 100, 2) } else { 0 }

# Create markdown report
$ReportContent = @"
# DEMONSTRATION REPORT FOR Q TICKETS API TESTING

## GENERAL INFORMATION

- **Test Date:** $(Get-Date)
- **Mode:** Demo with mock data
- **Purpose:** Show testing system functionality
- **API Token:** DEMO_TOKEN_***

## TESTING STATISTICS

| Metric | Value |
|---------|---------|
| Total Tests | $TotalTests |
| Successful | $PassedTests |
| Failed | $FailedTests |
| Success Rate | $SuccessRate% |

## RESULTS BY CATEGORIES

### ORDERS
✅ Test 1.1: Get all orders list (200)
✅ Test 1.2: Get paid orders list (200)
✅ Test 1.6: Get specific order #4360 (200)

### CLIENTS
✅ Test 2.1: Get clients list (200)
✅ Test 2.3: Create client (201)

### EVENTS
✅ Test 3.1: Get events list (200)
✅ Test 3.3: Get specific event #33 (200)

### DISCOUNTS
✅ Test 4.1: Get price colors list (200)

### BARCODES
✅ Test 5.1: Get tickets barcodes list (200)

### PARTNERS API
✅ Test 6.1: Add ticket (single) (201)
✅ Test 6.8: Check seats status (batch) (200)
✅ Test 6.12: Find tickets by barcode (200)

### ERROR TESTS
❌ Test 7.1: Authorization check (invalid token) (401)
❌ Test 7.2: Check non-existent order (404)
❌ Test 7.4: Check with empty body where required (400)

## TESTING FILES

- **Full results:** `$RESULTS_FILE`
- **Test logs:** `$LOG_DIR/`

## NEXT STEPS

1. **Get real API token** from Qtickets personal cabinet
2. **Run full test:** `.\run_tests.ps1 YOUR_API_TOKEN`
3. **Study real API responses**
4. **Adapt IDs** for your system

## CONCLUSION

Demonstration completed successfully! System is ready for full testing.

**For real testing use:** `.\run_tests.ps1 YOUR_API_TOKEN`

**Completion time:** $(Get-Date)
"@

$ReportContent | Out-File -FilePath $SUMMARY_FILE -Encoding UTF8

# Final statistics
Write-Host "`n=========================================" -ForegroundColor Blue
Write-Host "DEMONSTRATION COMPLETED" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "STATISTICS:" -ForegroundColor Yellow
Write-Host "   Total tests: $TotalTests"
Write-Host "   Successful: $PassedTests" -ForegroundColor Green
Write-Host "   Failed: $FailedTests" -ForegroundColor Red
Write-Host "   Success rate: $SuccessRate%" -ForegroundColor Yellow
Write-Host "FILES:" -ForegroundColor Yellow
Write-Host "   Report: $SUMMARY_FILE"
Write-Host "   Results: $RESULTS_FILE"
Write-Host "   Logs: $LOG_DIR/"
Write-Host "========================================="
Write-Host ""
Write-Host "Demo run completed!" -ForegroundColor Green
Write-Host "View report: $SUMMARY_FILE" -ForegroundColor Cyan
Write-Host "For real testing: .\run_tests.ps1 YOUR_API_TOKEN" -ForegroundColor Yellow
Write-Host "========================================="
