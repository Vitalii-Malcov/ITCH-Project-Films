class FirecrawlError(Exception):
    """Базовая ошибка интеграции Firecrawl."""


class FirecrawlConfigurationError(FirecrawlError):
    """Ошибка конфигурации Firecrawl."""


class FirecrawlConnectionError(FirecrawlError):
    """Ошибка соединения с Firecrawl."""


class FirecrawlRateLimitError(FirecrawlError):
    """Превышен лимит запросов Firecrawl."""


class FirecrawlValidationError(FirecrawlError):
    """Некорректные входные данные Firecrawl."""