# Regex Tester API

Test, validate, and explain regex patterns via a simple HTTP API.

## Endpoints

### POST /test
Test a regex pattern against text.

**Body:**
```json
{
  "pattern": "\\d{3}-\\d{2}",
  "text": "SSN: 123-45-6789",
  "flags": ["i"]
}
```

**Response:**
```json
{
  "matches": ["123-45"],
  "match_count": 1,
  "indices": [{"start": 5, "end": 10, "group": "123-45"}],
  "valid": true
}
```

### POST /validate
Check if a regex pattern compiles.

**Body:**
```json
{"pattern": "([a-z]+"}
```

**Response:**
```json
{"valid": false, "pattern": "([a-z]+", "error": "unbalanced parenthesis"}
```

### POST /explain
Explain regex components.

**Body:**
```json
{"pattern": "\\d{3}-\\d{2}-\\d{4}"}
```

**Response:**
```json
{
  "explanation": "Pattern: \\d{3}-\\d{2}-\\d{4}\nComponents: any digit (0-9), quantifier {3}, ...",
  "components": ["any digit (0-9)", "quantifier {3}", ...],
  "valid": true
}
```

### GET /health
Health check endpoint.

## Flags
Supports: `i` (IGNORECASE), `m` (MULTILINE), `s` (DOTALL), `x` (VERBOSE), `a` (ASCII), `l` (LOCALE)

## Example
```bash
curl -X POST https://regex-tester.vercel.app/test \
  -H "Content-Type: application/json" \
  -d '{"pattern": "\\b[A-Z]{2,}\\b", "text": "Hello WORLD from Python"}'
```

## Rate Limit
60 requests per minute per IP.