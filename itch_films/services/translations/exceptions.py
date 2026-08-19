"""
Иерархия исключений модуля translations.

Та же идея, что и в services/ai_posters/exceptions.py: один базовый
класс, чтобы вызывающий код мог ловить все ошибки перевода разом,
и подклассы — чтобы реагировать на конкретные случаи (например,
не задан API-ключ) по-разному.
"""


class TranslationError(Exception):
    """Базовое исключение для всех ошибок модуля translations."""

    def __init__(self, message: str, details: str = ""):
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{super().__str__()} | {self.details}"
        return super().__str__()


class TranslationConfigurationError(TranslationError):
    """Выбрасывается, когда отсутствует или недействителен OPENAI_API_KEY."""


class TranslationRateLimitError(TranslationError):
    """Выбрасывается при превышении лимита запросов OpenAI API."""
