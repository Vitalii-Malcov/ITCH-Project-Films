import logging
import os

from dotenv import load_dotenv
from firecrawl import V1FirecrawlApp

from .exceptions import (
    FirecrawlConfigurationError,
    FirecrawlConnectionError,
    FirecrawlError,
    FirecrawlRateLimitError,
    FirecrawlValidationError,
)
from .models import CrawlResult, FirecrawlResult, SearchResult

# "network" — этот файл целиком про HTTP-вызовы к внешнему API
# Firecrawl (см. logging_setup.py: logs/network.log).
logger = logging.getLogger("network")


class FirecrawlClient:
    """Клиент для работы с Firecrawl API."""

    def __init__(self, api_key: str | None = None) -> None:
        load_dotenv()
        key = api_key or os.getenv("FIRECRAWL_API_KEY")
        if not key:
            raise FirecrawlConfigurationError(
                "FIRECRAWL_API_KEY не задана в аргументе конструктора или переменных окружения"
            )
        self._app = V1FirecrawlApp(api_key=key)

    # ------------------------------------------------------------------
    # Публичные методы
    # ------------------------------------------------------------------

    def scrape(self, url: str) -> FirecrawlResult:
        """Скрейпит одну страницу и возвращает FirecrawlResult."""
        self._validate_url(url)
        logger.info("Scraping: %s", url)
        try:
            response = self._app.scrape_url(url, formats=["markdown"])
            return FirecrawlResult(
                url=response.url or url,
                title=response.title or "",
                markdown=response.markdown or "",
            )
        except FirecrawlError:
            raise
        except Exception as exc:
            self._raise_mapped(exc, context=url)

    def crawl(self, url: str, limit: int = 10) -> CrawlResult:
        """Обходит сайт по ссылкам (до limit страниц)."""
        self._validate_url(url)
        if not isinstance(limit, int) or limit < 1:
            raise FirecrawlValidationError("limit должен быть положительным целым числом")
        logger.info("Crawling: %s (limit=%d)", url, limit)
        try:
            response = self._app.crawl_url(url, limit=limit)
            pages = []
            for doc in response.data or []:
                page_url = getattr(doc, "url", None) or url
                pages.append(FirecrawlResult(
                    url=page_url,
                    title=getattr(doc, "title", "") or "",
                    markdown=getattr(doc, "markdown", "") or "",
                ))
            return CrawlResult(url=url, pages=pages)
        except FirecrawlError:
            raise
        except Exception as exc:
            self._raise_mapped(exc, context=url)

    def search(self, query: str, limit: int = 5) -> SearchResult:
        """Ищет страницы через Firecrawl и возвращает SearchResult."""
        if not isinstance(query, str) or not query.strip():
            raise FirecrawlValidationError("query должен быть непустой строкой")
        if not isinstance(limit, int) or limit < 1:
            raise FirecrawlValidationError("limit должен быть положительным целым числом")
        logger.info("Searching: '%s'", query)
        try:
            response = self._app.search(query, limit=limit)
            # response.data — List[V1FirecrawlDocument] (Pydantic models), конвертируем через _to_dict
            results = [self._to_dict(doc) for doc in (response.data or [])]
            return SearchResult(query=query, results=results)
        except FirecrawlError:
            raise
        except Exception as exc:
            self._raise_mapped(exc, context=query)

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(value) -> dict:
        """Безопасно конвертирует dict или Pydantic-модель в dict."""
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump(exclude_none=True)
        if hasattr(value, "dict"):
            return value.dict(exclude_none=True)
        raise FirecrawlError(
            f"Firecrawl вернул неподдерживаемый тип данных: {type(value).__name__}"
        )

    @staticmethod
    def _validate_url(url: str) -> None:
        """Проверяет, что URL непустой и начинается с http:// или https://."""
        if not url or not isinstance(url, str):
            raise FirecrawlValidationError("URL должен быть непустой строкой")
        if not url.startswith(("http://", "https://")):
            raise FirecrawlValidationError(f"URL должен начинаться с http:// или https://: {url!r}")

    @staticmethod
    def _raise_mapped(exc: Exception, context: str) -> None:
        """Преобразует исключение SDK в исключение нашего модуля."""
        status_code = getattr(exc, "status_code", None)
        if status_code is None:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)

        if status_code == 429:
            logger.warning("Rate limit exceeded: %s", context)
            raise FirecrawlRateLimitError("Превышен лимит запросов Firecrawl") from exc

        error_class = type(exc).__name__.lower()
        if any(word in error_class for word in ("connect", "timeout", "network")):
            logger.error("Connection error [%s]: %s", context, exc)
            raise FirecrawlConnectionError("Ошибка соединения с Firecrawl") from exc

        logger.error("Firecrawl error [%s]: %s", context, exc)
        raise FirecrawlError("Ошибка выполнения запроса Firecrawl") from exc