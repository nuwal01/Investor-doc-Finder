# Financial Report Finder API Documentation

## Overview

The Financial Report Finder API provides programmatic access to SEC EDGAR filings and investor relations documents. It parses natural language queries and returns structured results with direct links to official financial documents.

## Base URL

```
Development: http://localhost:3001/api
Production: https://your-domain.com/api
```

## Authentication

Currently, the API does not require authentication. Rate limiting is applied per IP address.

## Rate Limiting

- **20 requests per minute** per IP address
- Exceeding this limit returns `429 Too Many Requests`

---

## Endpoints

### Health Check

Check if the API server is running.

```
GET /health
```

#### Response

```json
{
  "status": "ok",
  "timestamp": "2026-01-27T12:00:00.000Z"
}
```

---

### Search Documents

Search for financial documents using natural language queries.

```
POST /api/search
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Natural language search query |

#### Example Request

```json
{
  "query": "Tesla 10-K 2024"
}
```

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Original search query |
| `parsed` | object | Parsed query components |
| `parsed.company` | string | Identified company name |
| `parsed.ticker` | string | Company ticker symbol (if identified) |
| `parsed.documentType` | string | Document type (annual, quarterly, etc.) |
| `parsed.year` | number | Filing year |
| `parsed.quarter` | number | Quarter number (1-4, if applicable) |
| `parsed.filingType` | string | SEC filing type (10-K, 10-Q, 8-K, etc.) |
| `results` | array | Search results |
| `timestamp` | string | ISO 8601 timestamp |

#### Result Object

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Direct URL to the document |
| `title` | string | Document title |
| `company` | string | Company name |
| `ticker` | string | Ticker symbol |
| `documentType` | string | Type of document |
| `filingDate` | string | Date the document was filed |
| `fileFormat` | string | File format (PDF, HTML, etc.) |
| `confidence` | number | Match confidence score (0-1) |
| `source` | string | Data source (sec-edgar, company-website) |

#### Example Response

```json
{
  "query": "Tesla 10-K 2024",
  "parsed": {
    "company": "Tesla",
    "ticker": "TSLA",
    "documentType": "annual",
    "year": 2024,
    "filingType": "10-K"
  },
  "results": [
    {
      "url": "https://www.sec.gov/Archives/edgar/data/1318605/000156459025004599/tsla-10k_20241231.htm",
      "title": "Tesla, Inc. - 10-K (2025-01-29)",
      "company": "Tesla, Inc.",
      "ticker": "TSLA",
      "documentType": "annual",
      "filingDate": "2025-01-29",
      "fileFormat": "HTML",
      "confidence": 0.95,
      "source": "sec-edgar"
    }
  ],
  "timestamp": "2026-01-27T12:00:00.000Z"
}
```

#### Error Responses

**400 Bad Request** - Invalid or missing query

```json
{
  "error": "Invalid query",
  "message": "Query parameter is required and must be a non-empty string"
}
```

**400 Bad Request** - Could not parse company

```json
{
  "error": "Could not parse query",
  "message": "Unable to identify company name from query. Please try rephrasing."
}
```

**500 Internal Server Error**

```json
{
  "error": "Search failed",
  "message": "Error details..."
}
```

---

### Company Autocomplete

Get company name suggestions for autocomplete functionality.

```
GET /api/autocomplete
```

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | Yes | - | Search query (min 1 character) |
| `limit` | number | No | 10 | Maximum results (max 20) |

#### Example Request

```
GET /api/autocomplete?q=App&limit=5
```

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Original query |
| `suggestions` | array | Company suggestions |
| `count` | number | Number of suggestions returned |

#### Suggestion Object

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Company name |
| `ticker` | string | Ticker symbol |
| `cik` | string | SEC CIK number |

#### Example Response

```json
{
  "query": "App",
  "suggestions": [
    {
      "name": "Apple",
      "ticker": "AAPL",
      "cik": "0000320193"
    },
    {
      "name": "Applied Materials",
      "ticker": "AMAT",
      "cik": "0000006951"
    }
  ],
  "count": 2
}
```

---

## Supported Query Formats

The API supports various natural language query formats:

### Company Identification
- Company name: `"Apple annual report"`
- Ticker symbol: `"AAPL 10-K"`
- Variations: `"MSFT"`, `"Microsoft"`, `"microsoft corp"`

### Document Types
- Annual Reports: `"10-K"`, `"annual report"`
- Quarterly Reports: `"10-Q"`, `"quarterly earnings"`, `"Q3 results"`
- Current Reports: `"8-K"`
- Proxy Statements: `"proxy"`, `"DEF 14A"`
- Investor Presentations: `"investor presentation"`, `"investor deck"`
- ESG Reports: `"ESG report"`, `"sustainability report"`

### Time Periods
- Year: `"2024"`, `"2023"`
- Quarter: `"Q1"`, `"Q2"`, `"Q3"`, `"Q4"`, `"first quarter"`

### Example Queries
- `"Apple Q4 2024 earnings"`
- `"TSLA annual report 2023"`
- `"Microsoft investor presentation September 2024"`
- `"Amazon 10-K 2023"`
- `"Google quarterly results Q2 2024"`

---

## Supported Companies

The API supports **100+ S&P 500 companies** with direct CIK mapping for faster lookups. Other companies are searched via SEC EDGAR full-text search.

### Major Supported Companies

| Sector | Companies |
|--------|-----------|
| Technology | Apple, Microsoft, Alphabet/Google, Amazon, NVIDIA, Meta, Tesla, Oracle, Salesforce, Adobe, Cisco, Intel, AMD |
| Financial | JPMorgan Chase, Visa, Mastercard, Bank of America, Goldman Sachs, Morgan Stanley, BlackRock, PayPal |
| Healthcare | UnitedHealth, Eli Lilly, Johnson & Johnson, Pfizer, Merck, AbbVie, Amgen |
| Consumer | Walmart, Costco, Procter & Gamble, Coca-Cola, PepsiCo, Nike, McDonald's, Starbucks |
| Energy | Exxon Mobil, Chevron, ConocoPhillips, Schlumberger |
| Industrial | General Electric, Boeing, Caterpillar, Honeywell, UPS, Lockheed Martin |
| Communication | Netflix, Disney, Comcast, Verizon, AT&T |

---

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Route not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

---

## Code Examples

### JavaScript/TypeScript

```typescript
const response = await fetch('http://localhost:3001/api/search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ query: 'Apple 10-K 2024' }),
});

const data = await response.json();
console.log(data.results);
```

### Python

```python
import requests

response = requests.post(
    'http://localhost:3001/api/search',
    json={'query': 'Apple 10-K 2024'}
)

data = response.json()
print(data['results'])
```

### cURL

```bash
curl -X POST http://localhost:3001/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Apple 10-K 2024"}'
```

---

## Data Sources

1. **SEC EDGAR** (Primary)
   - Direct access to official SEC filings
   - Forms: 10-K, 10-Q, 8-K, DEF 14A, and more
   - CIK-based lookup for known companies
   - Full-text search for other companies

2. **Company Investor Relations** (Planned)
   - Direct links to company IR pages
   - Investor presentations and earnings calls
   - Additional document formats

---

## Changelog

### v1.0.0 (Current)
- Natural language query parsing
- SEC EDGAR integration
- Company autocomplete
- Rate limiting
- S&P 500 company support
