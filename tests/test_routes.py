"""
Flask API route tests.

All external services (Firecrawl, MongoDB) are replaced with mocks.
No real network connections. No real database writes or reads.

Routes tested:
  POST /api/scrape
  POST /api/search
  POST /api/extract   (stub, returns 501)
  GET  /api/history/<collection>

Note: This project has no /, /search, or /stats HTML routes.
Those belong to the itch_films sub-project (itch_films/).
"""
import pytest
from unittest.mock import MagicMock

from services.firecrawl.models import FirecrawlResult
from services.firecrawl.exceptions import (
    FirecrawlConfigurationError,
    FirecrawlRateLimitError,
    FirecrawlConnectionError,
    FirecrawlError,
    FirecrawlValidationError,
)


# ──────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_mongo(monkeypatch):
    """Replace the module-level MongoService instance in the route with a mock.

    Patched here (not in conftest) because mongo is created at import time.
    We monkeypatch the *attribute* on the already-imported module object.
    """
    import app.routes.firecrawl as route_module
    mock = MagicMock()
    mock.save_scrape.return_value = "test_doc_id"
    mock.save_crawl.return_value = "test_doc_id"
    mock.save_search.return_value = "test_doc_id"
    mock.get_recent.return_value = []
    monkeypatch.setattr(route_module, "mongo", mock)


def _mock_fc_client(scrape_result=None, scrape_raises=None):
    """Build a lightweight mock FirecrawlClient.

    Does NOT instantiate the real FirecrawlClient or touch V1FirecrawlApp.
    """
    mock = MagicMock()
    if scrape_raises is not None:
        mock.scrape.side_effect = scrape_raises
    elif scrape_result is not None:
        mock.scrape.return_value = scrape_result
    return mock


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/scrape
# ──────────────────────────────────────────────────────────────────────────────

class TestScrapeEndpoint:

    def test_missing_url_returns_400(self, client):
        resp = client.post("/api/scrape", json={})
        assert resp.status_code == 400

    def test_no_json_body_returns_4xx(self, client):
        # Flask 3.x returns 415 (Unsupported Media Type) when Content-Type
        # is missing entirely; both 400 and 415 indicate invalid input.
        resp = client.post("/api/scrape")
        assert resp.status_code in (400, 415)

    def test_successful_scrape_returns_200_with_fields(self, client, monkeypatch):
        import app.routes.firecrawl as route_module
        result = FirecrawlResult(
            url="https://example.com",
            title="Example Domain",
            markdown="# Example",
        )
        monkeypatch.setattr(
            route_module, "get_firecrawl_client",
            lambda: _mock_fc_client(scrape_result=result),
        )
        resp = client.post("/api/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["url"] == "https://example.com"
        assert body["title"] == "Example Domain"
        assert "_id" in body

    def test_no_firecrawl_key_returns_503(self, client, monkeypatch):
        import app.routes.firecrawl as route_module

        def _raise():
            raise FirecrawlConfigurationError("no key")

        monkeypatch.setattr(route_module, "get_firecrawl_client", _raise)
        resp = client.post("/api/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 503
        body = resp.get_json()
        assert "error" in body

    def test_rate_limit_returns_429(self, client, monkeypatch):
        import app.routes.firecrawl as route_module
        monkeypatch.setattr(
            route_module, "get_firecrawl_client",
            lambda: _mock_fc_client(scrape_raises=FirecrawlRateLimitError("rate limit")),
        )
        resp = client.post("/api/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 429

    def test_connection_error_returns_503(self, client, monkeypatch):
        import app.routes.firecrawl as route_module
        monkeypatch.setattr(
            route_module, "get_firecrawl_client",
            lambda: _mock_fc_client(scrape_raises=FirecrawlConnectionError("conn failed")),
        )
        resp = client.post("/api/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 503

    def test_validation_error_returns_400(self, client, monkeypatch):
        import app.routes.firecrawl as route_module
        monkeypatch.setattr(
            route_module, "get_firecrawl_client",
            lambda: _mock_fc_client(scrape_raises=FirecrawlValidationError("bad url")),
        )
        resp = client.post("/api/scrape", json={"url": "not-a-url"})
        assert resp.status_code == 400

    def test_generic_firecrawl_error_returns_500(self, client, monkeypatch):
        import app.routes.firecrawl as route_module
        monkeypatch.setattr(
            route_module, "get_firecrawl_client",
            lambda: _mock_fc_client(scrape_raises=FirecrawlError("unknown")),
        )
        resp = client.post("/api/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/search
# ──────────────────────────────────────────────────────────────────────────────

class TestSearchEndpoint:

    def test_missing_query_returns_400(self, client):
        resp = client.post("/api/search", json={})
        assert resp.status_code == 400

    def test_no_json_body_returns_4xx(self, client):
        # Flask 3.x returns 415 (Unsupported Media Type) when Content-Type
        # is missing entirely; both 400 and 415 indicate invalid input.
        resp = client.post("/api/search")
        assert resp.status_code in (400, 415)

    def test_no_firecrawl_key_returns_503(self, client, monkeypatch):
        import app.routes.firecrawl as route_module

        def _raise():
            raise FirecrawlConfigurationError("no key")

        monkeypatch.setattr(route_module, "get_firecrawl_client", _raise)
        resp = client.post("/api/search", json={"query": "python"})
        assert resp.status_code == 503


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/extract  (not yet implemented)
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractEndpoint:

    def test_extract_returns_501(self, client):
        resp = client.post("/api/extract", json={"url": "https://example.com", "schema": {}})
        assert resp.status_code == 501

    def test_extract_body_contains_error_key(self, client):
        resp = client.post("/api/extract", json={"url": "https://example.com", "schema": {}})
        body = resp.get_json()
        assert "error" in body


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/history/<collection>
# ──────────────────────────────────────────────────────────────────────────────

class TestHistoryEndpoint:

    def test_scrapes_collection_returns_200(self, client):
        resp = client.get("/api/history/scrapes")
        assert resp.status_code == 200

    def test_searches_collection_returns_200(self, client):
        resp = client.get("/api/history/searches")
        assert resp.status_code == 200

    def test_crawls_collection_returns_200(self, client):
        resp = client.get("/api/history/crawls")
        assert resp.status_code == 200

    def test_response_contains_collection_field(self, client):
        resp = client.get("/api/history/scrapes")
        body = resp.get_json()
        assert body["collection"] == "scrapes"
        assert "results" in body

    def test_unknown_collection_returns_400(self, client):
        resp = client.get("/api/history/unknown")
        assert resp.status_code == 400

    def test_unknown_collection_response_contains_error(self, client):
        resp = client.get("/api/history/hack_attempt")
        body = resp.get_json()
        assert "error" in body

    def test_limit_param_is_accepted(self, client):
        resp = client.get("/api/history/scrapes?limit=5")
        assert resp.status_code == 200