"""
MockProvider — заглушка для разработки, реализующая AIImageProvider.

Что делает:
    Генерирует WebP-изображение сплошного цвета через Pillow.
    Цвет выбирается по жанровым/стилевым подсказкам в промпте,
    поэтому постер каждого фильма хотя бы отличается оттенком.

Почему Pillow, а не чистый Python:
    WebP — сложный бинарный формат. Написать корректные WebP-байты вручную
    означает реализовать битовый поток VP8L — сотни строк кода.
    Pillow кодирует изображение одной строкой и создаёт настоящий WebP-файл,
    который браузеры и Flask могут отдавать напрямую.

Заменить на настоящего провайдера, когда будет готов:
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

# Цветовая палитра, подобранная под дизайн ITCH Films — достаточно
# насыщенная, чтобы плейсхолдер оставался заметным на тёмном фоне сайта.
# Каждый жанр сопоставлен с RGB-кортежем, используемым как фон постера.
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
_DEFAULT_COLOR: tuple[int, int, int] = (80, 80, 120)  # заметный сине-серый


def _color_from_prompt(prompt: str) -> tuple[int, int, int]:
    """Выбирает цвет фона по жанровым ключевым словам в промпте."""
    prompt_lower = prompt.lower()
    for genre, color in _GENRE_COLORS.items():
        if genre in prompt_lower:
            return color
    return _DEFAULT_COLOR


class MockProvider(AIImageProvider):
    """
    Генерирует WebP сплошного цвета без обращения к внешнему API.
    Безопасен для использования в разработке, CI и демо-окружениях.
    """

    # Имитация задержки в секундах — делает тайминг реалистичным для тестов
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
                f"MockProvider сгенерировал WebP {width}×{height} "
                f"({len(webp_bytes)} байт) color={color}"
            )
            return webp_bytes

        except Exception as exc:
            raise ProviderError(
                "MockProvider failed to generate image.",
                provider=self.provider_name(),
                details=str(exc),
            ) from exc

    def health_check(self) -> bool:
        """MockProvider всегда доступен."""
        return True

    def provider_name(self) -> str:
        return 'mock'

    def model_name(self) -> str:
        return 'mock-v1'