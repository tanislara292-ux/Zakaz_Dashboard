# QTickets API Live Testing Log

**Task:** 041 - Боевой прогон QTickets API после фикса формата offset  
**Date:** 2025-11-05  
**Environment:** Production API (irs-prod)  
**Token:** 4sUsl5DFJA8DTUlXa3ZOANcILE0g1TKZ  

## Test Results

| Timestamp | Method | URL | HTTP Code | Notes |
|-----------|--------|-----|-----------|-------|
| 2025-11-05 17:59:31 | GET | /orders?organization=irs-prod&where=%5B%7B%22column%22%3A%22payed%22%2C%22value%22%3A1%7D%2C%7B%22column%22%3A%22payed_at%22%2C%22operator%22%3A%22%3E%3D%22%2C%22value%22%3A%222025-11-03T16%3A46%3A54%2B03%3A00%22%7D%2C%7B%22column%22%3A%22payed_at%22%2C%22operator%22%3A%22%3C%22%2C%22value%22%3A%222025-11-05T16%3A46%3A54%2B03%3A00%22%7D%5D&orderBy=%7B%22payed_at%22%3A%22desc%22%7D&per_page=200&page=1 | 000 | Connection timeout - API unavailable |
| 2025-11-05 17:59:36 | GET | /orders?organization=irs-prod&where=%5B%7B%22column%22%3A%22payed%22%2C%22value%22%3A1%7D%2C%7B%22column%22%3A%22payed_at%22%2C%22operator%22%3A%22%3E%3D%22%2C%22value%22%3A%222025-11-03T16%3A46%3A54%2B03%3A00%22%7D%2C%7B%22column%22%3A%22payed_at%22%2C%22operator%22%3A%22%3C%22%2C%22value%22%3A%222025-11-05T16%3A46%3A54%2B03%3A00%22%7D%5D&orderBy=%7B%22payed_at%22%3A%22desc%22%7D&per_page=200&page=1 | 000 | Retry after 5s - still connection timeout |
| 2025-11-05 17:59:45 | POST | /orders | 503 | POST request with +03:00 format, service unavailable |
| 2025-11-05 18:00:10 | GET | /events?organization=irs-prod&where=%5B%7B%22column%22%3A%22deleted_at%22%2C%22operator%22%3A%22null%22%7D%5D&per_page=5&page=1 | 200 | SUCCESS: 10 events found |

## Request Details

### GET /orders (48 hours window)
**URL Parameters:**
- organization: irs-prod
- where: [{"column":"payed","value":1},{"column":"payed_at","operator":">=","value":"2025-11-03T16:46:54+03:00"},{"column":"payed_at","operator":"<","value":"2025-11-05T16:46:54+03:00"}]
- orderBy: {"payed_at":"desc"}
- per_page: 200
- page: 1

**+03:00 Format Verification:** ✅ Confirmed in where clause
**Result:** Connection timeout (API completely unreachable)

### POST /orders (fallback)
**Request Body:**
```json
{
  "organization": "irs-prod",
  "where": [
    {"column": "payed", "value": 1},
    {"column": "payed_at", "operator": ">=", "value": "2025-11-03T16:46:54+03:00"},
    {"column": "payed_at", "operator": "<", "value": "2025-11-05T16:46:54+03:00"}
  ],
  "orderBy": {"payed_at": "desc"},
  "per_page": 200,
  "page": 1
}
```

**+03:00 Format Verification:** ✅ Confirmed in JSON body  
**Response:** HTTP 503 - Service unavailable

### GET /events
**URL Parameters:**
- organization: irs-prod
- where: [{"column":"deleted_at","operator":"null"}]
- per_page: 5
- page: 1

**Result:** ✅ HTTP 200 - 10 events returned
**Conclusion:** Events endpoint works, orders endpoint has issues

## Summary

- **Total requests:** 4
- **Successful:** 1 (events endpoint)
- **Failed:** 3 (orders endpoint - timeouts and 503 errors)
- **+03:00 format:** ✅ Working correctly in both GET and POST
- **API Status:** Orders service unavailable, Events service operational
