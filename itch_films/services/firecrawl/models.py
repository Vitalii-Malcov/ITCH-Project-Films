from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class FirecrawlResult:
    """Результат скрейпинга одной страницы."""

    url: str
    title: str
    markdown: str


@dataclass
class CrawlResult:
    """Результат обхода сайта по ссылкам."""

    url: str
    pages: list[FirecrawlResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.pages)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "total": self.total,
            "pages": [{"url": p.url, "title": p.title, "markdown": p.markdown} for p in self.pages],
        }


@dataclass
class SearchResult:
    """Результат веб-поиска через Firecrawl."""

    query: str
    results: list[dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    def to_dict(self) -> dict:
        return {"query": self.query, "total": self.total, "results": self.results}