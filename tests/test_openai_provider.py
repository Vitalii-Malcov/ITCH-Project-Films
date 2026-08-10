"""
Unit tests for OpenAIProvider.

Rules:
    - No real OpenAI API calls — openai.OpenAI is mocked throughout.
    - No .env is loaded — env vars are set via monkeypatch.
    - No file I/O — images are inspected in memory.
    - Tests are independent.
"""

import base64
import io
import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_png_bytes(width: int = 4, height: int = 4) -> bytes:
    """Return raw bytes of a minimal valid PNG image."""
    from PIL import Image
    img = Image.new("RGB", (width, height), color=(80, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_webp_bytes(width: int = 4, height: int = 4) -> bytes:
    """Return raw bytes of a minimal valid WebP image."""
    from PIL import Image
    img = Image.new("RGB", (width, height), color=(30, 60, 90))
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=80)
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _make_provider(model: str = "gpt-image-2") -> "OpenAIProvider":
    """
    Build an OpenAIProvider with a MagicMock client.

    openai.OpenAI is patched during __init__ to prevent any real HTTP client.
    _client is then replaced with a fresh MagicMock for per-test configuration.
    """
    from services.ai_posters.providers.openai_provider import OpenAIProvider
    with patch("openai.OpenAI"):
        provider = OpenAIProvider(api_key="test-key-placeholder", model=model)
    provider._client = MagicMock()
    return provider


def _mock_b64_response(image_bytes: bytes) -> MagicMock:
    """Build a mock API response with b64_json image data."""
    item = MagicMock()
    item.b64_json = _b64(image_bytes)
    item.url = None
    resp = MagicMock()
    resp.data = [item]
    return resp


# ── 1. Initialisation ─────────────────────────────────────────────────────────

class TestOpenAIProviderInit:

    def test_missing_key_raises_configuration_error(self, monkeypatch):
        from services.ai_posters.providers.openai_provider import OpenAIProvider
        from services.ai_posters.exceptions import ProviderConfigurationError

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ProviderConfigurationError):
            OpenAIProvider()

    def test_explicit_key_creates_provider(self, monkeypatch):
        from services.ai_posters.providers.openai_provider import OpenAIProvider

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("openai.OpenAI"):
            provider = OpenAIProvider(api_key="sk-test")

        assert provider.provider_name() == "openai"

    def test_env_key_is_used_when_no_explicit_arg(self, monkeypatch):
        from services.ai_posters.providers.openai_provider import OpenAIProvider

        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        with patch("openai.OpenAI"):
            provider = OpenAIProvider()

        assert provider.provider_name() == "openai"

    def test_default_model_is_gpt_image_2(self, monkeypatch):
        from services.ai_posters.providers.openai_provider import OpenAIProvider, DEFAULT_MODEL

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
        with patch("openai.OpenAI"):
            provider = OpenAIProvider(api_key="sk-test")

        assert provider.model_name() == DEFAULT_MODEL
        assert provider.model_name() == "gpt-image-2"

    def test_model_overridden_by_constructor_arg(self, monkeypatch):
        from services.ai_posters.providers.openai_provider import OpenAIProvider

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("openai.OpenAI"):
            provider = OpenAIProvider(api_key="sk-test", model="dall-e-3")

        assert provider.model_name() == "dall-e-3"

    def test_model_overridden_by_env_var(self, monkeypatch):
        from services.ai_posters.providers.openai_provider import OpenAIProvider

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_IMAGE_MODEL", "dall-e-3")
        with patch("openai.OpenAI"):
            provider = OpenAIProvider()

        assert provider.model_name() == "dall-e-3"


# ── 2. Size mapping ───────────────────────────────────────────────────────────

class TestSizeMappingGptImage:
    """GPT Image (gpt-image-2) uses 1024x1536 portrait, 1536x1024 landscape."""

    @pytest.fixture
    def provider(self):
        return _make_provider(model="gpt-image-2")

    def test_portrait_maps_to_1024x1536(self, provider):
        assert provider._map_size(640, 960) == "1024x1536"

    def test_landscape_maps_to_1536x1024(self, provider):
        assert provider._map_size(960, 640) == "1536x1024"

    def test_square_maps_to_1024x1024(self, provider):
        assert provider._map_size(1024, 1024) == "1024x1024"

    def test_default_poster_dims_give_portrait(self, provider):
        """PosterService default 640x960 should produce GPT Image portrait size."""
        assert provider._map_size(640, 960) == "1024x1536"


class TestSizeMappingDalle3:
    """DALL-E 3 keeps its own valid sizes."""

    @pytest.fixture
    def provider(self):
        return _make_provider(model="dall-e-3")

    def test_portrait_maps_to_1024x1792(self, provider):
        assert provider._map_size(640, 960) == "1024x1792"

    def test_landscape_maps_to_1792x1024(self, provider):
        assert provider._map_size(960, 640) == "1792x1024"

    def test_square_maps_to_1024x1024(self, provider):
        assert provider._map_size(1024, 1024) == "1024x1024"


class TestSizeMappingDalle2:
    """DALL-E 2 snaps to nearest supported square."""

    def test_snaps_to_512(self):
        provider = _make_provider(model="dall-e-2")
        assert provider._map_size(512, 512) == "512x512"

    def test_snaps_to_256_for_small(self):
        provider = _make_provider(model="dall-e-2")
        assert provider._map_size(100, 100) == "256x256"


# ── 3. API params (GPT Image path) ───────────────────────────────────────────

class TestApiParamsGptImage:

    @pytest.fixture
    def provider(self):
        return _make_provider(model="gpt-image-2")

    def _call_generate_and_get_kwargs(self, provider, **gen_kwargs) -> dict:
        """Generate with a mock response and return the API call kwargs."""
        provider._client.images.generate.return_value = _mock_b64_response(
            _make_webp_bytes()
        )
        provider.generate("test prompt", **gen_kwargs)
        return provider._client.images.generate.call_args.kwargs

    def test_api_called_with_quality_low(self, provider):
        """Default quality must be 'low'."""
        kwargs = self._call_generate_and_get_kwargs(provider)
        assert kwargs["quality"] == "low"

    def test_api_called_with_output_format_webp(self, provider):
        """Default output_format must be 'webp' for GPT Image."""
        kwargs = self._call_generate_and_get_kwargs(provider)
        assert kwargs["output_format"] == "webp"

    def test_api_called_with_output_compression(self, provider):
        """output_compression must be present for GPT Image."""
        kwargs = self._call_generate_and_get_kwargs(provider)
        assert "output_compression" in kwargs
        assert isinstance(kwargs["output_compression"], int)

    def test_api_called_with_correct_size(self, provider):
        kwargs = self._call_generate_and_get_kwargs(provider, width=640, height=960)
        assert kwargs["size"] == "1024x1536"

    def test_api_called_with_correct_model(self, provider):
        kwargs = self._call_generate_and_get_kwargs(provider)
        assert kwargs["model"] == "gpt-image-2"

    def test_gpt_image_does_not_use_response_format(self, provider):
        """GPT Image uses output_format, not the legacy response_format param."""
        kwargs = self._call_generate_and_get_kwargs(provider)
        assert "response_format" not in kwargs

    def test_dalle3_uses_response_format_not_output_format(self):
        """DALL-E 3 uses the legacy response_format='b64_json' path."""
        provider = _make_provider(model="dall-e-3")
        provider._client.images.generate.return_value = _mock_b64_response(
            _make_png_bytes()
        )
        provider.generate("test")
        kwargs = provider._client.images.generate.call_args.kwargs
        assert kwargs.get("response_format") == "b64_json"
        assert "output_format" not in kwargs


# ── 4. WebP output handling ───────────────────────────────────────────────────

class TestWebpHandling:

    @pytest.fixture
    def provider(self):
        return _make_provider()

    def test_native_webp_is_returned_unchanged(self, provider):
        """
        When the API returns WebP bytes, _ensure_webp() must pass them through
        without re-encoding (no quality loss, no Pillow roundtrip).
        """
        webp_bytes = _make_webp_bytes()
        provider._client.images.generate.return_value = _mock_b64_response(webp_bytes)

        result = provider.generate("poster prompt")

        # Result must be the exact same bytes (no re-encoding)
        assert result == webp_bytes

    def test_png_bytes_are_converted_to_webp(self, provider):
        """When the API returns PNG (DALL-E path), Pillow must convert to WebP."""
        from PIL import Image

        png_bytes = _make_png_bytes()
        provider._client.images.generate.return_value = _mock_b64_response(png_bytes)

        result = provider.generate("poster prompt")

        img = Image.open(io.BytesIO(result))
        assert img.format == "WEBP"

    def test_empty_bytes_raise_provider_error(self, provider):
        from services.ai_posters.exceptions import ProviderError
        with pytest.raises(ProviderError):
            provider._ensure_webp(b"")


# ── 5. Successful base64 generation ──────────────────────────────────────────

class TestGenerateBase64:

    @pytest.fixture
    def provider(self):
        return _make_provider()

    def test_returns_bytes(self, provider):
        provider._client.images.generate.return_value = _mock_b64_response(
            _make_webp_bytes()
        )
        result = provider.generate("cinematic poster")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_invalid_base64_raises_provider_error(self, provider):
        """Corrupt base64 must raise ProviderError, not a raw exception."""
        from services.ai_posters.exceptions import ProviderError

        item = MagicMock()
        item.b64_json = "!!!not valid base64!!!"
        item.url = None
        mock_resp = MagicMock()
        mock_resp.data = [item]
        provider._client.images.generate.return_value = mock_resp

        with pytest.raises(ProviderError):
            provider.generate("test")


# ── 6. URL fallback ───────────────────────────────────────────────────────────

class TestGenerateUrl:

    @pytest.fixture
    def provider(self):
        return _make_provider()

    def test_url_response_is_downloaded_and_ensured_webp(self, provider):
        """When b64_json is absent, image is downloaded from url."""
        from PIL import Image

        png = _make_png_bytes()
        item = MagicMock()
        item.b64_json = None
        item.url = "https://fake-openai.example.com/image.png"
        mock_resp = MagicMock()
        mock_resp.data = [item]
        provider._client.images.generate.return_value = mock_resp

        with patch.object(provider, "_download_url", return_value=png):
            result = provider.generate("cinematic poster")

        img = Image.open(io.BytesIO(result))
        assert img.format == "WEBP"


# ── 7. Empty / malformed response ────────────────────────────────────────────

class TestEmptyResponse:

    @pytest.fixture
    def provider(self):
        return _make_provider()

    def test_empty_data_list_raises_provider_error(self, provider):
        from services.ai_posters.exceptions import ProviderError
        mock_resp = MagicMock()
        mock_resp.data = []
        provider._client.images.generate.return_value = mock_resp
        with pytest.raises(ProviderError):
            provider.generate("test")

    def test_none_b64_and_none_url_raises_provider_error(self, provider):
        from services.ai_posters.exceptions import ProviderError
        item = MagicMock()
        item.b64_json = None
        item.url = None
        mock_resp = MagicMock()
        mock_resp.data = [item]
        provider._client.images.generate.return_value = mock_resp
        with pytest.raises(ProviderError):
            provider.generate("test")


# ── 8. SDK exception mapping ──────────────────────────────────────────────────

class TestExceptionMapping:

    @pytest.fixture
    def provider(self):
        return _make_provider()

    def test_auth_error_becomes_configuration_error(self, provider):
        import openai as oa
        from services.ai_posters.exceptions import ProviderConfigurationError

        provider._client.images.generate.side_effect = oa.AuthenticationError(
            message="Invalid key",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )
        with pytest.raises(ProviderConfigurationError):
            provider.generate("test")

    def test_rate_limit_error_becomes_rate_limit_error(self, provider):
        import openai as oa
        from services.ai_posters.exceptions import ProviderRateLimitError

        provider._client.images.generate.side_effect = oa.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        with pytest.raises(ProviderRateLimitError):
            provider.generate("test")

    def test_connection_error_becomes_provider_error(self, provider):
        import openai as oa
        from services.ai_posters.exceptions import ProviderError

        provider._client.images.generate.side_effect = oa.APIConnectionError(
            request=MagicMock(),
        )
        with pytest.raises(ProviderError):
            provider.generate("test")

    def test_api_status_error_becomes_provider_error(self, provider):
        import openai as oa
        from services.ai_posters.exceptions import ProviderError

        provider._client.images.generate.side_effect = oa.APIStatusError(
            message="Internal server error",
            response=MagicMock(status_code=500, headers={}),
            body=None,
        )
        with pytest.raises(ProviderError):
            provider.generate("test")

    def test_exception_chain_is_preserved(self, provider):
        import openai as oa
        from services.ai_posters.exceptions import ProviderRateLimitError

        original = oa.RateLimitError(
            message="Rate limit",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        provider._client.images.generate.side_effect = original
        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider.generate("test")
        assert exc_info.value.__cause__ is original


# ── 9. Provider identity ──────────────────────────────────────────────────────

class TestProviderIdentity:

    def test_provider_name(self):
        assert _make_provider().provider_name() == "openai"

    def test_model_name_matches_constructor_arg(self):
        assert _make_provider(model="dall-e-2").model_name() == "dall-e-2"