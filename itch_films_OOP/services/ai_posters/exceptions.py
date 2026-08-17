"""
Иерархия пользовательских исключений модуля ai_posters.

Зачем иерархия, а не одно общее исключение:
    Flask (или любой другой вызывающий код) может ловить PosterError,
    чтобы обработать все ошибки разом, или ловить конкретный подкласс,
    чтобы реагировать по-разному на каждый тип ошибки.
"""


class PosterError(Exception):
    """Базовое исключение для всех ошибок ai_posters."""

    def __init__(self, message: str, details: str = ""):
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{super().__str__()} | {self.details}"
        return super().__str__()


class ProviderError(PosterError):
    """Выбрасывается, когда AI-провайдер изображений падает или возвращает ошибку."""

    def __init__(self, message: str, provider: str = "", details: str = ""):
        self.provider = provider
        super().__init__(message, details)


class ProviderConfigurationError(ProviderError):
    """Выбрасывается, когда отсутствует обязательная настройка провайдера (например, API-ключ)."""


class ProviderRateLimitError(ProviderError):
    """Выбрасывается при превышении лимита запросов API провайдера."""


class StorageError(PosterError):
    """Выбрасывается при ошибке сохранения или чтения файла изображения."""


class RepositoryError(PosterError):
    """Выбрасывается при ошибке чтения или записи в базу данных."""