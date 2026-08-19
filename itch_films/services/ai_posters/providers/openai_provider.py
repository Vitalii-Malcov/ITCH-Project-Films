"""
OpenAIProvider — генерирует изображения постеров фильмов через OpenAI Images API.

Основная модель: gpt-image-2 (GPT Image, по умолчанию)
Обратно совместимый fallback: dall-e-3, dall-e-2

Правила проектирования:
    - Читает OPENAI_API_KEY из окружения; никогда из кода или local_settings.
    - Запрашивает WebP напрямую у GPT Image (output_format="webp").
    - Если API уже вернул байты WebP, пропускает перекодирование через Pillow.
    - Если API вернул PNG/JPEG (другие модели), конвертирует в WebP через Pillow.
    - Сопоставляет размеры вызывающего кода с корректным размером для активного
      семейства моделей.
    - seed молча игнорируется (не поддерживается ни одной текущей моделью
      изображений OpenAI).
    - style и negative_prompt добавляются в текстовый промпт, а не отправляются
      как отдельные параметры API, чтобы избежать различий API между моделями.
    - Выбрасывает подклассы ProviderError, чтобы PosterService ловил их единообразно.
"""

import base64
import io
import logging
import os
import urllib.request

import openai

from services.ai_posters.exceptions import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
)
from services.ai_posters.providers.base import AIImageProvider

logger = logging.getLogger(__name__)

# ── Значения по умолчанию — единый источник истины ────────────────────────────
DEFAULT_MODEL       = "gpt-image-2"
DEFAULT_QUALITY     = "low"         # "low" — самый дешёвый вариант, хорош для первых тестов
DEFAULT_OUTPUT_FMT  = "webp"        # GPT Image умеет отдавать WebP нативно
DEFAULT_COMPRESSION = 80            # 0–100, управляет качеством вывода WebP/JPEG

# ── Поддерживаемые размеры GPT Image (gpt-image-2) ────────────────────────────
_GPT_PORTRAIT   = "1024x1536"
_GPT_LANDSCAPE  = "1536x1024"
_GPT_SQUARE     = "1024x1024"

# ── Поддерживаемые размеры DALL-E 3 ────────────────────────────────────────────
_DALLE3_PORTRAIT  = "1024x1792"
_DALLE3_LANDSCAPE = "1792x1024"
_DALLE3_SQUARE    = "1024x1024"

# ── Поддерживаемые размеры DALL-E 2 (сначала самые крупные — для ближайшего подбора) ─
_DALLE2_SIZES = ["1024x1024", "512x512", "256x256"]


class OpenAIProvider(AIImageProvider):
    """
    Провайдер AI-изображений на основе OpenAI Images API.

    Модель по умолчанию: gpt-image-2 (семейство GPT Image).

    Использование:
        provider = OpenAIProvider()                        # читает переменные окружения
        provider = OpenAIProvider(api_key="sk-...")        # явный ключ
        provider = OpenAIProvider(model="dall-e-3")        # более старая модель
        provider = OpenAIProvider(quality="high")          # более высокое качество
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        quality: str | None = None,
        output_format: str | None = None,
        output_compression: int | None = None,
    ) -> None:
        """
        Аргументы:
            api_key:            Ключ OpenAI. По умолчанию берётся из env-переменной
                                OPENAI_API_KEY.
            model:              Название модели. По умолчанию из env-переменной
                                OPENAI_IMAGE_MODEL, затем из DEFAULT_MODEL ('gpt-image-2').
            quality:            Качество генерации. По умолчанию из env-переменной
                                OPENAI_IMAGE_QUALITY, затем из DEFAULT_QUALITY ('low').
            output_format:      Формат изображения. По умолчанию из env-переменной
                                OPENAI_IMAGE_FORMAT, затем из DEFAULT_OUTPUT_FMT ('webp').
            output_compression: Уровень сжатия 0–100. По умолчанию из env-переменной
                                OPENAI_IMAGE_COMPRESSION, затем 80.

        Исключения:
            ProviderConfigurationError: если API-ключ недоступен.
        """
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is not set. "
                "Add it to your .env file or pass api_key= explicitly.",
                provider="openai",
            )

        self._model = model or os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_MODEL)

        self._quality = quality or os.getenv("OPENAI_IMAGE_QUALITY", DEFAULT_QUALITY)

        self._output_fmt = (
            output_format or os.getenv("OPENAI_IMAGE_FORMAT", DEFAULT_OUTPUT_FMT)
        )

        _raw_compression = (
            output_compression
            if output_compression is not None
            else int(os.getenv("OPENAI_IMAGE_COMPRESSION", DEFAULT_COMPRESSION))
        )
        self._compression = _raw_compression

        self._client = openai.OpenAI(api_key=key)
        logger.debug(
            "OpenAIProvider init: model=%s quality=%s format=%s compression=%d",
            self._model, self._quality, self._output_fmt, self._compression,
        )

    # ── Интерфейс AIImageProvider ──────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 640,
        height: int = 960,
        seed: int | None = None,
        style: str = "",
    ) -> bytes:
        """
        Генерирует изображение постера и возвращает байты WebP.

        Заметки по параметрам:
            negative_prompt — добавляется в prompt как текст ("Avoid: ...").
                              У GPT Image нет отдельного параметра negative_prompt.
            style           — ожидается, что уже встроен в prompt через
                              prompt_builder.build_prompt(); передаётся отдельно
                              только когда непустой, как дополнительное уточнение.
            seed            — не поддерживается ни одной текущей моделью
                              изображений OpenAI; молча игнорируется.
            width / height  — сопоставляются с ближайшим поддерживаемым моделью
                              размером.

        Возвращает:
            Сырые байты WebP, готовые для PosterStorage.save().

        Исключения:
            ProviderConfigurationError: API-ключ недействителен или отозван.
            ProviderRateLimitError:     превышен лимит запросов.
            ProviderError:              любая другая ошибка API или декодирования.
        """
        if seed is not None:
            logger.debug("OpenAIProvider: seed ignored (not supported by OpenAI images API)")

        full_prompt = self._build_full_prompt(prompt, negative_prompt)
        size = self._map_size(width, height)
        api_params = self._build_api_params(full_prompt, size)

        logger.info(
            "OpenAIProvider.generate: model=%s size=%s quality=%s format=%s prompt_len=%d",
            self._model, size, self._quality, self._output_fmt, len(full_prompt),
        )

        try:
            response = self._client.images.generate(**api_params)
        except openai.AuthenticationError as exc:
            raise ProviderConfigurationError(
                "OpenAI API key is invalid or has been revoked.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc
        except openai.RateLimitError as exc:
            raise ProviderRateLimitError(
                "OpenAI rate limit exceeded. Wait before retrying.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc
        except openai.APIConnectionError as exc:
            raise ProviderError(
                "Cannot connect to OpenAI API. Check your network.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc
        except openai.APIStatusError as exc:
            raise ProviderError(
                f"OpenAI API returned HTTP {exc.status_code}.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc

        return self._extract_and_ensure_webp(response)

    def health_check(self) -> bool:
        """
        Возвращает True, если API доступен и модель существует.
        Использует models.retrieve() — значительно дешевле, чем генерация изображения.
        """
        try:
            self._client.models.retrieve(self._model)
            return True
        except openai.AuthenticationError:
            logger.error("OpenAIProvider health_check: authentication failed")
            return False
        except Exception as exc:
            logger.error("OpenAIProvider health_check failed: %s", exc)
            return False

    def provider_name(self) -> str:
        return "openai"

    def model_name(self) -> str:
        return self._model

    # ── Приватные вспомогательные методы ───────────────────────────────────────

    @staticmethod
    def _build_full_prompt(prompt: str, negative_prompt: str) -> str:
        """
        Встраивает negative_prompt в основной промпт как текстовое уточнение.
        У GPT Image нет отдельного параметра API negative_prompt.
        """
        if negative_prompt.strip():
            return f"{prompt}. Avoid: {negative_prompt.strip()}."
        return prompt

    def _map_size(self, width: int, height: int) -> str:
        """
        Сопоставляет запрошенные размеры с ближайшей строкой размера,
        поддерживаемой API.

        GPT Image (gpt-image-2): портрет 1024x1536, квадрат 1024x1024, альбом 1536x1024
        DALL-E 3:                 портрет 1024x1792, квадрат 1024x1024, альбом 1792x1024
        DALL-E 2:                 округляется до ближайшего из 1024, 512, 256 (только квадрат)
        """
        model = self._model.lower()

        if "gpt-image" in model:
            if width > height:
                return _GPT_LANDSCAPE
            if width < height:
                return _GPT_PORTRAIT
            return _GPT_SQUARE

        if "dall-e-3" in model:
            if width > height:
                return _DALLE3_LANDSCAPE
            if width < height:
                return _DALLE3_PORTRAIT
            return _DALLE3_SQUARE

        # DALL-E 2 и неизвестные модели: округляем до ближайшего поддерживаемого квадрата
        target = max(width, height)
        for size_str in _DALLE2_SIZES:
            side = int(size_str.split("x")[0])
            if target >= side:
                return size_str
        return _DALLE2_SIZES[-1]  # минимум 256x256

    def _build_api_params(self, full_prompt: str, size: str) -> dict:
        """
        Формирует словарь kwargs для images.generate() в зависимости от активной модели.

        GPT Image (gpt-image-2) поддерживает output_format, output_compression
        и quality. Модели DALL-E используют вместо этого response_format.
        """
        model = self._model.lower()

        params: dict = {
            "model":  self._model,
            "prompt": full_prompt,
            "size":   size,
            "n":      1,
        }

        if "gpt-image" in model:
            # Нативные параметры GPT Image — запрашивают WebP напрямую у API
            params["quality"]            = self._quality
            params["output_format"]      = self._output_fmt
            params["output_compression"] = self._compression
        else:
            # DALL-E 3 / DALL-E 2: используем устаревший response_format для доставки в b64
            params["response_format"] = "b64_json"

        return params

    def _extract_and_ensure_webp(self, response) -> bytes:
        """
        Извлекает байты изображения из ответа API и гарантирует вывод в WebP.

        Путь декодирования:
            есть b64_json → декодировать из base64 → _ensure_webp()
            есть url      → скачать          → _ensure_webp()  (fallback)
            нет ни того, ни другого → ProviderError
        """
        if not response.data:
            raise ProviderError(
                "OpenAI returned an empty response (no image data).",
                provider=self.provider_name(),
            )

        image_data = response.data[0]

        if image_data.b64_json:
            raw_bytes = self._decode_base64(image_data.b64_json)
        elif image_data.url:
            # Fallback через URL — путь для других моделей или response_format="url"
            raw_bytes = self._download_url(image_data.url)
        else:
            raise ProviderError(
                "OpenAI response contains neither b64_json nor url.",
                provider=self.provider_name(),
            )

        return self._ensure_webp(raw_bytes)

    def _decode_base64(self, b64_data: str) -> bytes:
        """Декодирует строку base64 и возвращает сырые байты."""
        try:
            return base64.b64decode(b64_data)
        except Exception as exc:
            raise ProviderError(
                "Failed to decode base64 image data from OpenAI.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc

    def _download_url(self, url: str) -> bytes:
        """Скачивает байты изображения по URL (fallback, когда b64_json отсутствует)."""
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except Exception as exc:
            raise ProviderError(
                "Failed to download image from OpenAI URL.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc

    def _ensure_webp(self, image_bytes: bytes) -> bytes:
        """
        Возвращает байты WebP.

        Если на входе уже WebP (например, GPT Image вернул output_format=webp),
        возвращается без изменений — без перекодирования, без потери качества.
        Иначе Pillow конвертирует PNG / JPEG / любой поддерживаемый формат в WebP.

        Выбрасывает ProviderError для пустых или нечитаемых данных.
        """
        if not image_bytes:
            raise ProviderError(
                "OpenAI returned empty image bytes.",
                provider=self.provider_name(),
            )

        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            if img.format == "WEBP":
                # Уже WebP — пропускаем перекодирование, чтобы не терять качество
                logger.debug("OpenAIProvider: API returned WebP natively, skipping re-encode")
                return image_bytes
            # PNG / JPEG / другое → WebP
            logger.debug(
                "OpenAIProvider: converting %s → WebP (compression=%d)",
                img.format, self._compression,
            )
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=self._compression)
            return buf.getvalue()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                "Failed to ensure WebP format.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc