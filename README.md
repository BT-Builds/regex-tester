# Regex Tester API

Validate, test, and manipulate regex patterns via HTTP API.

## Endpoints

### `GET /health`
Health check - no auth required.

### `POST /validate`
Validate a regex pattern syntax.

```bash
curl -X POST https://regex-tester.vercel.app/validate \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "^[a-z]+$"}'
```

### `POST /test`
Test if pattern matches text.

```bash
curl -X POST https://regex-tester.vercel.app/test \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "\\d{3}-\\d{3}-\\d{4}", "text": "Call 555-123-4567"}'
```

### `POST /extract`
Extract all matches from text.

```bash
curl -X POST https://regex-tester.vercel.app/extract \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "\\d+", "text": "Order 123 shipped on 2024-01-15"}'
```

### `POST /replace`
Replace matches in text.

```bash
curl -X POST https://regex-tester.vercel.app/replace \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"pattern": "\\d{3}-\\d{3}-\\d{4}", "text": "Call 555-123-4567", "replacement": "[REDACTED]"}'
```

### `GET /explain/{pattern}`
Get basic explanation of regex pattern constructs.

```bash
curl https://regex-tester.vercel.app/explain/\\d+
```

## Flags
- `i` - Case insensitive
- `m` - Multiline
- `s` - Dot matches newline
- `x` - Verbose mode

## Pricing
List on RapidAPI for $15-29/month team plans.