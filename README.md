# Business Listing Scraper API

A production-ready FastAPI service that ingests an array of listing URLs, scrapes each page concurrently, and returns normalised business records aligned with the Prisma `Business` model.

## Features

- Async, rate-limited HTTP client built on `httpx`
- Structured data (JSON-LD, Microdata) extraction with `extruct`
- Heuristic HTML parsing with `selectolax` for resilient fallback
- Automatic deduplication by listing URL/title
- Optional PostgreSQL persistence aligned with the shared Prisma schema
- Background cron scheduler (default every 6 hours) with scrape telemetry logging
- Configurable concurrency, retry, and timeout settings via environment variables
- Structured logging with Loguru
- Test suite with `pytest` and `respx`

## Getting Started

### Prerequisites

- Python 3.9+
- [Poetry](https://python-poetry.org/) for dependency management

### Installation

```bash
poetry install
```

### Running the Test Suite

```bash
poetry run pytest
```

### Launching the API

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Database & Prisma Schema

- Set `SCRAPER_DATABASE_URL` to a PostgreSQL connection string that uses the `asyncpg` driver (for example: `postgresql+asyncpg://postgres:postgres@localhost:5432/prisma`).
- The canonical schema is stored in `prisma/schema.prisma`, mirroring the models consumed by your Node.js/Prisma services.
- Apply migrations and `prisma generate` from your JavaScript project so both services share the same tables.
- When configured, the scraper persists businesses into the shared `businesses` table while preventing duplicates by `listing_url`.

### Background Scheduler & Telemetry

- The FastAPI app launches a background cron job whenever `SCRAPER_DATABASE_URL` is present and `SCRAPER_ENABLE_SCHEDULER` (default `true`) is not disabled.
- Control the cadence with `SCRAPER_CRON_INTERVAL_HOURS` (default `6`).
- Each run stores an audit entry in the `scraper_details` table with timestamps, counts, duplicates, and error details so downstream systems can monitor progress.
- Use the `/ingest` endpoint to trigger an immediate scrape cycle for smoke tests or manual backfills.

### Docker

Build and run the service in a container:

```bash
docker build -t business-scraper .
docker run --rm -p 8000:8000 \
  -e SCRAPER_DATABASE_URL="postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/prisma" \
  -e SCRAPER_ENABLE_SCHEDULER=true \
  business-scraper
```

### API Usage

`POST /scrape`

```json
{
  "urls": [
    "https://www.businessesforsale.com/search/businesses-for-sale"
  ],
  "maxConcurrency": 6
}
```

Example response (truncated):

```json
{
  "businesses": [
    {
      "title": "Sample Business",
      "listingUrl": "https://example.com/listing/sample",
      "location": "London, United Kingdom",
      "price": "£250,000",
      "description": "Profitable business with loyal customers.",
      "images": ["https://example.com/images/sample-1.jpg"],
      "allLinks": ["https://example.com/listing/sample"]
    }
  ],
  "errors": [],
  "meta": {
    "totalRequested": 1,
    "totalSucceeded": 1,
    "totalBusinesses": 12,
    "durationMs": 1824
  }
}
```

## Configuration

Environment variables (prefixed with `SCRAPER_`) can override defaults from `app/core/config.py`. For example:

- `SCRAPER_HTTP_MAX_CONCURRENCY`
- `SCRAPER_HTTP_TIMEOUT_SECONDS`
- `SCRAPER_REQUEST_MAX_URLS`
- `SCRAPER_JUNK_TITLE_KEYWORDS`
- `SCRAPER_JUNK_URL_KEYWORDS`
- `SCRAPER_USER_AGENT_POOL`
- `SCRAPER_DATABASE_URL`
- `SCRAPER_ENABLE_SCHEDULER`
- `SCRAPER_CRON_INTERVAL_HOURS`

Create a `.env` file to persist local overrides.

### Handling Anti-Bot Protection

- Each request rotates through a configurable pool of desktop user agents and sets per-domain `Referer` headers.
- Automatic retries apply exponential backoff for transient 4xx/5xx responses.
- Some sites may still respond with HTTP 403 or other blocks. Provide session cookies, proxying, or additional custom headers via environment overrides if required.

## Extending Parsers

- Add structured-data transforms inside `app/scraper/structured.py`
- Add heuristic rules or site-specific logic in `app/scraper/heuristics.py`
- `app/scraper/extractor.py` merges signals and performs deduplication

## Project Structure

- `app/main.py` – FastAPI application entry point
- `app/scraper/` – scraping orchestration, HTTP client, extractors, utilities
- `app/db/` – SQLAlchemy models and session helpers mapped to the Prisma tables
- `app/services/` – database repository and scheduled ingestion logic
- `prisma/schema.prisma` – authoritative Prisma schema shared with the Node.js API
- `tests/` – unit tests and HTML fixtures

## License

MIT
