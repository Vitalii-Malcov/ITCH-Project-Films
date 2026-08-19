# Firecrawl Service Module

Part of **Project_IT_Career_Hub_2**. Wraps the Firecrawl Python SDK into a clean,
typed interface for use by Flask routes and AI agents.

---

## Structure

```
services/firecrawl/
├── __init__.py       — public API, re-exports all names
├── client.py         — FirecrawlClient (main class)
├── models.py         — typed result dataclasses
└── exceptions.py     — custom exception hierarchy
```

---

## Public API

```python
from services.firecrawl import FirecrawlClient
from services.firecrawl import ScrapeResult, CrawlResult, SearchResult
from services.firecrawl import FirecrawlError, FirecrawlConnectionError, FirecrawlRateLimitError
```

---

## FirecrawlClient — methods

| Method | Description | Returns |
|--------|-------------|---------|
| `scrape(url)` | Scrape a single page | `ScrapeResult` |
| `crawl(url, limit=10)` | Crawl site following links | `CrawlResult` |
| `search(query, limit=5)` | Web search via Firecrawl | `SearchResult` |
| `extract(url, schema)` | Structured data extraction | `dict` |

---

## Models

### ScrapeResult
| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | Page URL |
| `title` | `str` | Page title |
| `markdown` | `str` | Page content as Markdown |
| `metadata` | `dict` | Raw metadata from Firecrawl |

`.to_dict()` — returns dict ready for MongoDB or JSON response.

### CrawlResult
| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | Root URL crawled |
| `pages` | `list[ScrapeResult]` | All crawled pages |
| `total` | `int` | Total pages count |

### SearchResult
| Field | Type | Description |
|-------|------|-------------|
| `query` | `str` | Search query |
| `results` | `list[dict]` | Raw results from API |
| `total` | `int` | Total results count |

---

## Exception hierarchy

```
FirecrawlError                — base, catches everything
├── FirecrawlConnectionError  — network / timeout issues  → HTTP 503
└── FirecrawlRateLimitError   — API rate limit exceeded   → HTTP 429
```

---

## Usage example

```python
from services.firecrawl import FirecrawlClient, FirecrawlError

client = FirecrawlClient()

try:
    result = client.scrape("https://example.com")
    print(result.title)
    print(result.markdown[:500])
except FirecrawlError as e:
    print(f"Error: {e}")
```

---

## Configuration

Requires `FIRECRAWL_API_KEY` in `.env`:

```
FIRECRAWL_API_KEY=your_key_here
```

---

## Future integrations

- **Flask** — import `FirecrawlClient` in route handlers
- **MongoDB** — use `result.to_dict()` before `insert_one()`
- **OpenAI / Claude** — pass `result.markdown` as context to AI agents
