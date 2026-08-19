"""
Unit-тесты для OpenAIProvider.

Правила:
    - Никаких реальных вызовов OpenAI API — openai.OpenAI замокан везде.
    - .env не загружается — переменные окружения задаются через monkeypatch.
    - Никакого файлового I/O — изображения проверяются в памяти.
    - Тесты независимы.
"""

import base64
import io
import pytest
from unittest.mock import MagicMock, patch


# ── Вспомогательные функции ───────────────────────────────────────────────────────────

def _make_png_bytes(width: int = 4, height: int = 4) -> bytes:
    """Возвращает сырые байты минимально корректного PNG-изображения."""
    from PIL import Image
    img = Image.new("RGB", (width, height), color=(80, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_webp_bytes(width: int = 4, height: int = 4) -> bytes:
    """Возвращает сырые байты минимально корректного WebP-изображения."""
    from PIL import Image
    img = Image.new("RGB", (width, height), color=(30, 60, 90))
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=80)
    return buf.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _make_provider(model: str = "gpt-image-2") -> "OpenAIProvider":
    """
    Строит OpenAIProvider с клиентом-MagicMock.

    openai.OpenAI патчится во время __init__, чтобы не создавался реальный HTTP-клиент.
    Затем _client заменяется на свежий MagicMock для настройки в каждом тесте.
    """
    from services.ai_posters.providers.openai_provider import OpenAIProvider
    with patch("openai.OpenAI"):
        provider = OpenAIProvider(api_key="test-key-placeholder", model=model)
    provider._client = MagicMock()
    return provider


def _mock_b64_response(image_bytes: bytes) -> MagicMock:
    """Строит мок ответа API с данными изображения в b64_json."""
    item = MagicMock()
    item.b64_json = _b64(image_bytes)
    item.url = None
    resp = MagicMock()
    resp.data = [item]
    return resp


# ── 1. Инициализация ─────────────────────────────────────────────────────────

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


# ── 2. Сопоставление размеров ───────────────────────────────────────────────────────────

class TestSizeMappingGptImage:
    """GPT Image (gpt-image-2) использует 1024x1536 портрет, 1536x1024 альбом."""

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
        """Размеры по умолчанию PosterService 640x960 должны давать портретный размер GPT Image."""
        assert provider._map_size(640, 960) == "1024x1536"


class TestSizeMappingDalle3:
    """DALL-E 3 использует свои собственные допустимые размеры."""

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
    """DALL-E 2 округляется до ближайшего поддерживаемого квадрата."""

    def test_snaps_to_512(self):
        provider = _make_provider(model="dall-e-2")
        assert provider._map_size(512, 512) == "512x512"

    def test_snaps_to_256_for_small(self):
        provider = _make_provider(model="dall-e-2")
        assert provider._map_size(100, 100) == "256x256"


# ── 3. Параметры API (путь GPT Image) ───────────────────────────────────────────

class TestApiParamsGptImage:

    @pytest.fixture
    def provider(self):
        return _make_provider(model="gpt-image-2")

    def _call_generate_and_get_kwargs(self, provider, **gen_kwargs) -> dict:
        """Генерирует с моком ответа и возвращает kwargs вызова API."""
        provider._client.images.generate.return_value = _mock_b64_response(
            _make_webp_bytes()
        )
        provider.generate("test prompt", **gen_kwargs)
        return provider._client.images.generate.call_args.kwargs

    def test_api_called_with_quality_low(self, provider):
        """Качество по умолчанию должно быть 'low'."""
        kwargs = self._call_generate_and_get_kwargs(provider)
        assert kwargs["quality"] == "low"

    def test_api_called_with_output_format_webp(self, provider):
        """output_format по умолчанию должен быть 'webp' для GPT Image."""
        kwargs = self._call_generate_and_get_kwargs(provider)
        assert kwargs["output_format"] == "webp"

    def test_api_called_with_output_compression(self, provider):
        """output_compression должен присутствовать для GPT Image."""
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
        """GPT Image использует output_format, а не устаревший параметр response_format."""
        kwargs = self._call_generate_and_get_kwargs(provider)
        assert "response_format" not in kwargs

    def test_dalle3_uses_response_format_not_output_format(self):
        """DALL-E 3 использует устаревший путь response_format='b64_json'."""
        provider = _make_provider(model="dall-e-3")
        provider._client.images.generate.return_value = _mock_b64_response(
            _make_png_bytes()
        )
        provider.generate("test")
        kwargs = provider._client.images.generate.call_args.kwargs
        assert kwargs.get("response_format") == "b64_json"
        assert "output_format" not in kwargs


# ── 4. Обработка WebP на выходе ───────────────────────────────────────────────────

class TestWebpHandling:

    @pytest.fixture
    def provider(self):
        return _make_provider()

    def test_native_webp_is_returned_unchanged(self, provider):
        """
        Когда API возвращает байты WebP, _ensure_webp() должен пропускать их
        без перекодирования (без потери качества, без прохода через Pillow).
        """
        webp_bytes = _make_webp_bytes()
        provider._client.images.generate.return_value = _mock_b64_response(webp_bytes)

        result = provider.generate("poster prompt")

        # Результат должен быть точно теми же байтами (без перекодирования)
        assert result == webp_bytes

    def test_png_bytes_are_converted_to_webp(self, provider):
        """Когда API возвращает PNG (путь DALL-E), Pillow должен конвертировать в WebP."""
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


# ── 5. Успешная генерация base64 ──────────────────────────────────────────

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
        """Повреждённый base64 должен выбрасывать ProviderError, а не сырое исключение."""
        from services.ai_posters.exceptions import ProviderError

        item = MagicMock()
        item.b64_json = "!!!not valid base64!!!"
        item.url = None
        mock_resp = MagicMock()
        mock_resp.data = [item]
        provider._client.images.generate.return_value = mock_resp

        with pytest.raises(ProviderError):
            provider.generate("test")


# ── 6. Fallback через URL ───────────────────────────────────────────────────────────

class TestGenerateUrl:

    @pytest.fixture
    def provider(self):
        return _make_provider()

    def test_url_response_is_downloaded_and_ensured_webp(self, provider):
        """Когда b64_json отсутствует, изображение скачивается по url."""
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


# ── 7. Пустой / некорректный ответ ────────────────────────────────────────────

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


# ── 8. Маппинг исключений SDK ──────────────────────────────────────────────────

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


# ── 9. Идентичность провайдера ──────────────────────────────────────────────────────

class TestProviderIdentity:

    def test_provider_name(self):
        assert _make_provider().provider_name() == "openai"

    def test_model_name_matches_constructor_arg(self):
        assert _make_provider(model="dall-e-2").model_name() == "dall-e-2"
