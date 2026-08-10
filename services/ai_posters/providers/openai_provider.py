"""
OpenAIProvider — generates movie poster images using the OpenAI Images API.

Primary model: gpt-image-2 (GPT Image, default)
Backward-compatible fallback: dall-e-3, dall-e-2

Design rules:
    - Reads OPENAI_API_KEY from env; never from code or local_settings.
    - Requests WebP directly from GPT Image (output_format="webp").
    - If the API already returns WebP bytes, skips Pillow re-encoding.
    - If the API returns PNG/JPEG (other models), converts to WebP via Pillow.
    - Maps caller dimensions to the correct size for the active model family.
    - seed is silently ignored (not supported by any current OpenAI image model).
    - style and negative_prompt are appended to the text prompt, not sent as
      separate API parameters, to avoid model-specific API differences.
    - Raises ProviderError subclasses so PosterService catches them uniformly.
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

# ── Defaults — single source of truth ────────────────────────────────────────
DEFAULT_MODEL       = "gpt-image-2"
DEFAULT_QUALITY     = "low"         # "low" is cheapest — good for first tests
DEFAULT_OUTPUT_FMT  = "webp"        # GPT Image can return WebP natively
DEFAULT_COMPRESSION = 80            # 0–100, controls WebP/JPEG output quality

# ── GPT Image (gpt-image-2) supported sizes ───────────────────────────────────
_GPT_PORTRAIT   = "1024x1536"
_GPT_LANDSCAPE  = "1536x1024"
_GPT_SQUARE     = "1024x1024"

# ── DALL-E 3 supported sizes ──────────────────────────────────────────────────
_DALLE3_PORTRAIT  = "1024x1792"
_DALLE3_LANDSCAPE = "1792x1024"
_DALLE3_SQUARE    = "1024x1024"

# ── DALL-E 2 supported sizes (largest-first for nearest-fit) ─────────────────
_DALLE2_SIZES = ["1024x1024", "512x512", "256x256"]


class OpenAIProvider(AIImageProvider):
    """
    AI image provider backed by OpenAI Images API.

    Default model: gpt-image-2 (GPT Image family).

    Usage:
        provider = OpenAIProvider()                        # reads env vars
        provider = OpenAIProvider(api_key="sk-...")        # explicit key
        provider = OpenAIProvider(model="dall-e-3")        # older model
        provider = OpenAIProvider(quality="high")          # higher quality
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
        Args:
            api_key:            OpenAI key. Falls back to OPENAI_API_KEY env var.
            model:              Model name. Falls back to OPENAI_IMAGE_MODEL env var,
                                then to DEFAULT_MODEL ('gpt-image-2').
            quality:            Generation quality. Falls back to OPENAI_IMAGE_QUALITY
                                env var, then to DEFAULT_QUALITY ('low').
            output_format:      Image format. Falls back to OPENAI_IMAGE_FORMAT env var,
                                then to DEFAULT_OUTPUT_FMT ('webp').
            output_compression: Compression level 0–100. Falls back to
                                OPENAI_IMAGE_COMPRESSION env var, then 80.

        Raises:
            ProviderConfigurationError: If no API key is available.
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

    # ── AIImageProvider interface ──────────────────────────────────────────────

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
        Generate a poster image and return WebP bytes.

        Parameter notes:
            negative_prompt — appended to prompt as text ("Avoid: ...").
                              GPT Image has no dedicated negative_prompt param.
            style           — expected to be already embedded in prompt by
                              prompt_builder.build_prompt(); passed separately
                              only when non-empty, as an additional clause.
            seed            — not supported by any current OpenAI image model;
                              silently ignored.
            width / height  — mapped to the nearest size the model supports.

        Returns:
            Raw WebP bytes ready for PosterStorage.save().

        Raises:
            ProviderConfigurationError: API key is invalid or revoked.
            ProviderRateLimitError:     Rate limit exceeded.
            ProviderError:              Any other API or decoding failure.
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
        Return True if the API is reachable and the model exists.
        Uses models.retrieve() — much cheaper than generating an image.
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

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_full_prompt(prompt: str, negative_prompt: str) -> str:
        """
        Merge negative_prompt into the main prompt as a text guidance clause.
        GPT Image has no dedicated negative_prompt API parameter.
        """
        if negative_prompt.strip():
            return f"{prompt}. Avoid: {negative_prompt.strip()}."
        return prompt

    def _map_size(self, width: int, height: int) -> str:
        """
        Map requested dimensions to the nearest API-supported size string.

        GPT Image (gpt-image-2): portrait 1024x1536, square 1024x1024, landscape 1536x1024
        DALL-E 3:                 portrait 1024x1792, square 1024x1024, landscape 1792x1024
        DALL-E 2:                 snaps to nearest of 1024, 512, 256 (square only)
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

        # DALL-E 2 and unknown models: snap to nearest supported square
        target = max(width, height)
        for size_str in _DALLE2_SIZES:
            side = int(size_str.split("x")[0])
            if target >= side:
                return size_str
        return _DALLE2_SIZES[-1]  # minimum 256x256

    def _build_api_params(self, full_prompt: str, size: str) -> dict:
        """
        Construct the kwargs dict for images.generate() based on the active model.

        GPT Image (gpt-image-2) supports output_format, output_compression,
        and quality. DALL-E models use response_format instead.
        """
        model = self._model.lower()

        params: dict = {
            "model":  self._model,
            "prompt": full_prompt,
            "size":   size,
            "n":      1,
        }

        if "gpt-image" in model:
            # GPT Image native params — requests WebP directly from the API
            params["quality"]            = self._quality
            params["output_format"]      = self._output_fmt
            params["output_compression"] = self._compression
        else:
            # DALL-E 3 / DALL-E 2: use legacy response_format for b64 delivery
            params["response_format"] = "b64_json"

        return params

    def _extract_and_ensure_webp(self, response) -> bytes:
        """
        Extract image bytes from the API response and guarantee WebP output.

        Decoding path:
            b64_json present → base64 decode → _ensure_webp()
            url present      → download      → _ensure_webp()  (fallback)
            neither          → ProviderError
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
            # URL fallback — other models or response_format="url" path
            raw_bytes = self._download_url(image_data.url)
        else:
            raise ProviderError(
                "OpenAI response contains neither b64_json nor url.",
                provider=self.provider_name(),
            )

        return self._ensure_webp(raw_bytes)

    def _decode_base64(self, b64_data: str) -> bytes:
        """Decode a base64 string and return raw bytes."""
        try:
            return base64.b64decode(b64_data)
        except Exception as exc:
            raise ProviderError(
                "Failed to decode base64 image data from OpenAI.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc

    def _download_url(self, url: str) -> bytes:
        """Download image bytes from a URL (fallback when b64_json is absent)."""
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
        Return WebP bytes.

        If the input is already WebP (e.g. GPT Image returned output_format=webp),
        it is returned unchanged — no re-encoding, no quality loss.
        Otherwise Pillow converts PNG / JPEG / any supported format to WebP.

        Raises ProviderError for empty or unreadable input.
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
                # Already WebP — skip re-encoding to avoid quality loss
                logger.debug("OpenAIProvider: API returned WebP natively, skipping re-encode")
                return image_bytes
            # PNG / JPEG / other → WebP
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