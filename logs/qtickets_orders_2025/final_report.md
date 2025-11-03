# QTickets API 2025 Sales Investigation Report

**Investigation Date:** 2025-11-03
**Organization:** irs-prod
**Objective:** Verify presence of fresh sales data from 2025

## Executive Summary

**Result:** ❌ **NO 2025 SALES DATA FOUND**

The QTickets API consistently returns only historical data from 2021, regardless of query parameters, date filters, or endpoint variations. All attempts to retrieve 2025 sales data failed.

## Detailed Investigation Results

### Step 0: Environment Configuration
- **API Base URL:** https://qtickets.ru/api/rest/v1
- **Organization:** irs-prod
- **Auth Token:** 4sUs*** (masked)
- **Timezone:** Europe/Moscow
- **Status:** ✅ Configuration loaded successfully

### Step A: Direct API Queries (GET requests)

| Step | Query Parameters | HTTP Status | Orders Count | Date Range | Result |
|------|------------------|-------------|--------------|------------|---------|
| A1 | `payed=1&since=2025-10-04T16:55:12+0300` | 200 OK | 50 | 2021-05-18 to 2021-05-31 | ❌ Returns 2021 data |
| A2 | `payed=1&since=2025-10-27T16:56:38+0300` | 200 OK | 50 | 2021-05-18 to 2021-05-31 | ❌ Returns 2021 data |
| A3 | `payed=1&since=2025-11-02T16:57:09+0300` | 200 OK | 50 | 2021-05-18 to 2021-05-31 | ❌ Returns 2021 data |

**Key Finding:** API completely ignores `since` parameter filtering

### Step B: Individual Order Testing

| Order ID | HTTP Status | Order Date | Status | Result |
|----------|-------------|------------|--------|---------|
| 1614202 | 200 OK | 2021-05-18T12:23:40+03:00 | paid | ✅ Individual order query works |

**Note:** Individual order retrieval works correctly, but still returns 2021 data

### Step C: Status Parameter Experiments

| Step | Parameters | HTTP Status | Orders Count | Result |
|------|------------|-------------|--------------|---------|
| C1 | `payed=1&status=paid&since=2025-10-04` | 200 OK | 50 | ❌ Same 2021 data |
| C2 | `status=paid&since=2025-10-04` | 200 OK | 50 | ❌ Same 2021 data |
| C3 | `status=completed&since=2025-10-04` | 200 OK | 50 | ❌ Same 2021 data |

**Finding:** Status parameters don't affect date filtering behavior

### Step D: POST Endpoint Testing

| Endpoint | HTTP Status | Response | Result |
|----------|-------------|----------|---------|
| `/orders/filter` | 404 Not Found | HTML 404 page | ❌ Endpoint doesn't exist |
| `/orders` | 503 Service Unavailable | `{"error":"Unknown error","status":503}` | ❌ Service unavailable |

**Finding:** POST endpoints are non-functional

## Sample API Response (2021 Data)

```json
{
  "data": [
    {
      "id": 1614202,
      "uniqid": "vKZDyV8tF2",
      "payed": true,
      "payed_at": "2021-05-18T12:23:40+03:00",
      "price": 4,
      "original_price": 390,
      "currency_id": "RUB"
    }
  ]
}
```

## Root Cause Analysis

**Primary Issue:** QTickets API appears to have broken date filtering functionality. The `since` parameter is completely ignored, causing the API to always return the same historical dataset from 2021.

**Secondary Issues:**
1. POST endpoints (`/orders/filter`, `/orders`) are non-functional
2. No alternative method to filter by recent dates
3. API documentation may be outdated or incorrect

## Business Impact

- **❌ No 2025 sales data accessible** via API
- **❌ Cannot load recent transactions** into dashboard
- **❌ Real-time analytics impossible**
- **❌ Production deployment blocked**

## Recommendations

### Immediate Actions Required

1. **🚨 Escalate to QTickets Support**
   - Submit critical bug report for broken `since` parameter
   - Request timeline for fix
   - Ask for alternative methods to access recent data

2. **📧 Include All Evidence**
   - Full API request/response logs
   - Multiple test cases with different date ranges
   - POST endpoint failure evidence

3. **⏸️ Suspend Production Deployment**
   - Cannot proceed with production deployment
   - Dashboard will show outdated 2021 data only

### Alternative Solutions (Short-term)

1. **Manual Data Export**
   - Request QTickets to provide manual CSV export of 2025 data
   - Implement one-time import mechanism

2. **Web Scraping (Last Resort)**
   - Investigate web admin interface for data extraction
   - Verify terms of service compliance

3. **Different Integration Approach**
   - Explore webhook implementations if available
   - Check for alternative API endpoints

## Technical Evidence Package

All investigation artifacts are archived in:
- **Archive:** `qtickets_orders_2025.tar.gz`
- **Contents:** Complete request/response logs, headers, body content
- **Size:** Full evidence package with timestamps

## Conclusion

**The QTickets API is fundamentally broken for recent data access.** Despite successful authentication and valid query construction, the API returns only 2021 data regardless of date parameters. This represents a critical blocking issue requiring immediate escalation to QTickets technical support.

**Next Steps:** Do not proceed with production deployment until API functionality is restored and verified with working 2025 data access.

---

**Investigation completed:** 2025-11-03
**Status:** BLOCKED - Vendor action required
**Priority:** CRITICAL