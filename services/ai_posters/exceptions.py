"""
Custom exception hierarchy for the ai_posters module.

Why a hierarchy instead of one generic exception:
    Flask (or any caller) can catch PosterError to handle all failures,
    or catch a specific subclass to react differently to each failure type.
"""


class PosterError(Exception):
    """Base exception for all ai_posters errors."""

    def __init__(self, message: str, details: str = ""):
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{super().__str__()} | {self.details}"
        return super().__str__()


class ProviderError(PosterError):
    """Raised when the AI image provider fails or returns an error response."""

    def __init__(self, message: str, provider: str = "", details: str = ""):
        self.provider = provider
        super().__init__(message, details)


class ProviderConfigurationError(ProviderError):
    """Raised when a required provider configuration is missing (e.g. API key)."""


class ProviderRateLimitError(ProviderError):
    """Raised when the provider API rate limit is exceeded."""


class StorageError(PosterError):
    """Raised when saving or reading an image file fails."""


class RepositoryError(PosterError):
    """Raised when a database read or write operation fails."""