"""
MockProvider — development placeholder for AIImageProvider.

What it does:
    Generates a solid-colour WebP image using Pillow.
    The colour is picked from the genre/style hints in the prompt,
    so each film's poster at least differs by hue.

Why Pillow instead of pure Python:
    WebP is a complex binary format. Writing valid WebP bytes manually
    requires implementing the VP8L bitstream — hundreds of lines.
    Pillow handles encoding in one line and produces a real WebP file
    that browsers and Flask can serve directly.

Replace this with a real provider when ready:
    class OpenAIProvider(AIImageProvider): ...
    service = PosterService(provider=OpenAIProvider(...), ...)
"""

import io
import time
import random
import logging

from services.ai_posters.providers.base import AIImageProvider
from services.ai_posters.exceptions import ProviderError

logger = logging.getLogger(__name__)

# Colour palette matching ITCH Films design — saturated enough to stay
# visible as a placeholder tile against the site's dark theme background.
# Each genre maps to an RGB tuple used as the poster background.
_GENRE_COLORS: dict[str, tuple[int, int, int]] = {
    'action':      (120, 45, 30),
    'horror':      (45,  40, 90),
    'comedy':      (90,  130, 50),
    'romance':     (130, 40, 70),
    'sci-fi':      (30,  70, 160),
    'animation':   (100, 70, 150),
    'drama':       (70,  65, 100),
    'documentary': (40,  90, 90),
    'thriller':    (90,  60, 30),
    'family':      (90,  110, 70),
    'music':       (140, 40, 130),
    'sports':      (40,  120, 60),
}
_DEFAULT_COLOR: tuple[int, int, int] = (80, 80, 120)  # visible blue-grey


def _color_from_prompt(prompt: str) -> tuple[int, int, int]:
    """Pick a background colour based on genre keywords in the prompt."""
    prompt_lower = prompt.lower()
    for genre, color in _GENRE_COLORS.items():
        if genre in prompt_lower:
            return color
    return _DEFAULT_COLOR


class MockProvider(AIImageProvider):
    """
    Generates a solid-colour WebP without calling any external API.
    Safe to use in development, CI, and demo environments.
    """

    # Simulated latency in seconds — keeps timing realistic for testing
    _FAKE_LATENCY: float = 0.05

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 640,
        height: int = 960,
        seed: int | None = None,
        style: str = "",
    ) -> bytes:
        try:
            from PIL import Image
        except ImportError as exc:
            raise ProviderError(
                "Pillow is required for MockProvider.",
                provider=self.provider_name(),
                details="Run: pip install Pillow",
            ) from exc

        try:
            time.sleep(self._FAKE_LATENCY)

            if seed is not None:
                random.seed(seed)

            color = _color_from_prompt(prompt)

            img = Image.new('RGB', (width, height), color=color)
            buf = io.BytesIO()
            img.save(buf, format='WEBP', quality=85)
            webp_bytes = buf.getvalue()

            logger.debug(
                f"MockProvider generated {width}×{height} WebP "
                f"({len(webp_bytes)} bytes) color={color}"
            )
            return webp_bytes

        except Exception as exc:
            raise ProviderError(
                "MockProvider failed to generate image.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc

    def health_check(self) -> bool:
        """MockProvider is always available."""
        return True

    def provider_name(self) -> str:
        return 'mock'

    def model_name(self) -> str:
        return 'mock-v1'