"""
Unit tests for FirecrawlClient.

Rules:
- No real Firecrawl API calls (V1FirecrawlApp is mocked).
- No real .env loading (load_dotenv is patched).
- No network access.
- Tests are independent — no shared mutable state.
"""
import pytest
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_client(api_key="test-key-placeholder"):
    """Build a FirecrawlClient with V1FirecrawlApp replaced by a MagicMock.

    Returns (client, mock_app) so tests can configure mock_app.scrape_url etc.
    The patch context is exited before returning; client._app remains the mock.
    """
    from services.firecrawl.client import FirecrawlClient

    mock_app = MagicMock()
    with patch("services.firecrawl.client.load_dotenv"):
        with patch("services.firecrawl.client.V1FirecrawlApp", return_value=mock_app):
            client = FirecrawlClient(api_key=api_key)
    # client._app was set to mock_app inside __init__; patch exit does not change it
    return client, mock_app


# ──────────────────────────────────────────────────────────────────────────────
# Initialization
# ──────────────────────────────────────────────────────────────────────────────

class TestFirecrawlClientInit:

    def test_missing_key_raises_configuration_error(self, monkeypatch):
        from services.firecrawl.client import FirecrawlClient
        from services.firecrawl.exceptions import FirecrawlConfigurationError

        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        with patch("services.firecrawl.client.load_dotenv"):
            with pytest.raises(FirecrawlConfigurationError):
                FirecrawlClient()

    def test_explicit_key_bypasses_env_var(self, monkeypatch):
        from services.firecrawl.client import FirecrawlClient

        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        with patch("services.firecrawl.client.load_dotenv"):
            with patch("services.firecrawl.client.V1FirecrawlApp"):
                client = FirecrawlClient(api_key="explicit-test-key")
        assert client is not None

    def test_env_key_is_used_when_no_explicit_arg(self, monkeypatch):
        from services.firecrawl.client import FirecrawlClient

        monkeypatch.setenv("FIRECRAWL_API_KEY", "env-test-key")
        with patch("services.firecrawl.client.load_dotenv"):
            with patch("services.firecrawl.client.V1FirecrawlApp"):
                client = FirecrawlClient()
        assert client is not None


# ──────────────────────────────────────────────────────────────────────────────
# URL validation
# ──────────────────────────────────────────────────────────────────────────────

class TestUrlValidation:

    @pytest.fixture()
    def fc(self):
        client, _ = _make_client()
        return client

    def test_empty_string_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.scrape("")

    def test_none_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.scrape(None)

    def test_bare_domain_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.scrape("example.com")

    def test_ftp_scheme_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.scrape("ftp://example.com")

    def test_https_url_passes_validation(self, fc):
        fc._app.scrape_url.return_value = MagicMock(
            url="https://example.com", title="Test", markdown="# Test"
        )
        from services.firecrawl.models import FirecrawlResult
        result = fc.scrape("https://example.com")
        assert isinstance(result, FirecrawlResult)

    def test_http_url_passes_validation(self, fc):
        fc._app.scrape_url.return_value = MagicMock(
            url="http://example.com", title="", markdown=""
        )
        result = fc.scrape("http://example.com")
        assert result.url == "http://example.com"


# ──────────────────────────────────────────────────────────────────────────────
# Scrape — successful response mapping
# ──────────────────────────────────────────────────────────────────────────────

class TestScrapeResponseMapping:

    @pytest.fixture()
    def fc(self):
        client, _ = _make_client()
        return client

    def test_fields_mapped_to_firecrawl_result(self, fc):
        from services.firecrawl.models import FirecrawlResult
        fc._app.scrape_url.return_value = MagicMock(
            url="https://example.com",
            title="Example Domain",
            markdown="# Example\n\nContent.",
        )
        result = fc.scrape("https://example.com")
        assert isinstance(result, FirecrawlResult)
        assert result.url == "https://example.com"
        assert result.title == "Example Domain"
        assert result.markdown == "# Example\n\nContent."

    def test_none_title_defaults_to_empty_string(self, fc):
        fc._app.scrape_url.return_value = MagicMock(
            url="https://x.com", title=None, markdown="text"
        )
        result = fc.scrape("https://x.com")
        assert result.title == ""

    def test_none_markdown_defaults_to_empty_string(self, fc):
        fc._app.scrape_url.return_value = MagicMock(
            url="https://x.com", title="T", markdown=None
        )
        result = fc.scrape("https://x.com")
        assert result.markdown == ""

    def test_none_url_falls_back_to_input(self, fc):
        fc._app.scrape_url.return_value = MagicMock(
            url=None, title="T", markdown="M"
        )
        result = fc.scrape("https://fallback.com")
        assert result.url == "https://fallback.com"


# ──────────────────────────────────────────────────────────────────────────────
# Exception mapping (_raise_mapped)
# ──────────────────────────────────────────────────────────────────────────────

class TestExceptionMapping:

    @pytest.fixture()
    def fc(self):
        client, _ = _make_client()
        return client

    def test_http_429_mapped_to_rate_limit_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlRateLimitError
        exc = Exception("Too Many Requests")
        exc.status_code = 429
        fc._app.scrape_url.side_effect = exc
        with pytest.raises(FirecrawlRateLimitError):
            fc.scrape("https://example.com")

    def test_connect_error_class_name_mapped_to_connection_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlConnectionError

        class ConnectError(Exception):
            pass

        fc._app.scrape_url.side_effect = ConnectError("failed to connect")
        with pytest.raises(FirecrawlConnectionError):
            fc.scrape("https://example.com")

    def test_timeout_error_class_name_mapped_to_connection_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlConnectionError

        class TimeoutError(Exception):
            pass

        fc._app.scrape_url.side_effect = TimeoutError("timed out")
        with pytest.raises(FirecrawlConnectionError):
            fc.scrape("https://example.com")

    def test_unknown_sdk_error_mapped_to_firecrawl_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlError
        fc._app.scrape_url.side_effect = ValueError("unexpected SDK error")
        with pytest.raises(FirecrawlError):
            fc.scrape("https://example.com")

    def test_our_exception_passes_through_unchanged(self, fc):
        from services.firecrawl.exceptions import FirecrawlRateLimitError
        original = FirecrawlRateLimitError("already mapped")
        fc._app.scrape_url.side_effect = original
        with pytest.raises(FirecrawlRateLimitError) as exc_info:
            fc.scrape("https://example.com")
        assert exc_info.value is original

    def test_exception_chain_preserved(self, fc):
        from services.firecrawl.exceptions import FirecrawlError
        original = ValueError("sdk error")
        fc._app.scrape_url.side_effect = original
        with pytest.raises(FirecrawlError) as exc_info:
            fc.scrape("https://example.com")
        assert exc_info.value.__cause__ is original


# ──────────────────────────────────────────────────────────────────────────────
# Search argument validation
# ──────────────────────────────────────────────────────────────────────────────

class TestSearchValidation:

    @pytest.fixture()
    def fc(self):
        client, _ = _make_client()
        return client

    def test_empty_query_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.search("")

    def test_whitespace_only_query_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.search("   ")

    def test_zero_limit_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.search("python", limit=0)

    def test_negative_limit_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.search("python", limit=-5)


# ──────────────────────────────────────────────────────────────────────────────
# Crawl argument validation
# ──────────────────────────────────────────────────────────────────────────────

class TestCrawlValidation:

    @pytest.fixture()
    def fc(self):
        client, _ = _make_client()
        return client

    def test_zero_limit_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.crawl("https://example.com", limit=0)

    def test_negative_limit_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.crawl("https://example.com", limit=-1)

    def test_invalid_url_raises_validation_error(self, fc):
        from services.firecrawl.exceptions import FirecrawlValidationError
        with pytest.raises(FirecrawlValidationError):
            fc.crawl("not-a-url", limit=5)