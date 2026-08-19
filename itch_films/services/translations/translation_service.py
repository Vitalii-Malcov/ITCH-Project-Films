"""
TranslationService — переводит одно описание фильма на русский через OpenAI.

Использует ту же OPENAI_API_KEY, что и services/ai_posters (никакого
нового ключа/аккаунта не нужно), но модель для перевода текста —
дешёвая gpt-4o-mini, а не модель генерации изображений.
"""

import logging
import os

import openai

from services.translations.exceptions import (
    TranslationConfigurationError,
    TranslationError,
    TranslationRateLimitError,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "Ты профессиональный переводчик синопсисов фильмов с английского на "
    "русский. Переводи естественно и художественно, сохраняя стиль краткого "
    "описания фильма. В ответе — только перевод, без кавычек и пояснений."
)


class TranslationService:
    """Переводит текст описания фильма на русский язык через OpenAI Chat API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise TranslationConfigurationError(
                "OPENAI_API_KEY не задана. Добавь её в .env или передай "
                "api_key= явно."
            )
        self._model = model or os.getenv("OPENAI_TRANSLATE_MODEL", DEFAULT_MODEL)
        self._client = openai.OpenAI(api_key=key)

    def translate(self, text: str) -> str:
        """
        Переводит text на русский. Пустая строка на входе → пустая строка
        на выходе (без обращения к API — незачем платить за перевод ничего).
        """
        if not text or not text.strip():
            return ""

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )
        except openai.AuthenticationError as exc:
            raise TranslationConfigurationError(
                "OpenAI API key is invalid or has been revoked.",
                details=str(exc),
            ) from exc
        except openai.RateLimitError as exc:
            raise TranslationRateLimitError(
                "OpenAI rate limit exceeded. Wait before retrying.",
                details=str(exc),
            ) from exc
        except openai.APIConnectionError as exc:
            raise TranslationError(
                "Cannot connect to OpenAI API. Check your network.",
                details=str(exc),
            ) from exc
        except openai.APIStatusError as exc:
            raise TranslationError(
                f"OpenAI API returned HTTP {exc.status_code}.",
                details=str(exc),
            ) from exc

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise TranslationError("OpenAI вернул пустой перевод.")
        return content.strip()
