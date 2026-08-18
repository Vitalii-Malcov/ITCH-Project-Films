# ─────────────────────────────────────────────
# app/services/film_news_service.py
# Поиск дополнительной информации о фильме через Firecrawl.
# routes.py вызывает только film_news_service.get_film_news()
# и не знает деталей Firecrawl.
# ─────────────────────────────────────────────

# services/firecrawl/ — собственная копия клиента внутри itch_films_OOP,
# импортируется благодаря sys.path на корень проекта из app/__init__.py.
from services.firecrawl import FirecrawlClient, FirecrawlError


class FilmNewsService:
    """
    Тонкая обёртка над FirecrawlClient для одной задачи: найти
    доп. информацию о фильме для блока «Подробнее» на карточке.

    Клиент создаётся лениво — при первом вызове get_film_news(), а не
    в конструкторе. Если инициализация не удалась (например, нет
    FIRECRAWL_API_KEY), self._client остаётся None и следующий вызов
    попробует создать клиент заново — это НЕ разовая попытка навсегда,
    а поведение "пробуем при каждом обращении, пока не получится".
    """

    def __init__(self):
        self._client: FirecrawlClient | None = None
        # Кэш по (нормализованное название, limit) — Firecrawl платный, а
        # каталог Sakila фиксирован (1000 фильмов), так что рост кэша
        # ограничен естественным образом; не нужна ни очистка, ни TTL.
        # Живёт, пока жив процесс — как и film_repository._genres_cache.
        self._cache: dict[tuple[str, int], list] = {}

    def _get_client(self) -> FirecrawlClient | None:
        if self._client is None:
            try:
                self._client = FirecrawlClient()
                print("[Firecrawl] Клиент инициализирован.")
            except Exception as e:
                print(f"[Firecrawl] Ошибка инициализации: {e}")
        return self._client

    def get_film_news(self, title: str, limit: int = 5) -> list:
        """
        Ищет доп. информацию о фильме (запрос "{title} film" находит
        Wikipedia/IMDb/Letterboxd — информационные страницы, а не
        только рецензии). При любой ошибке возвращает [] — сайт
        продолжает работать без этой фичи.

        Повторный запрос с тем же названием (без учёта регистра и
        лишних пробелов) отдаётся из кэша, а не тратит платный вызов
        Firecrawl заново.
        """
        cache_key = (title.strip().lower(), limit)
        if cache_key in self._cache:
            return self._cache[cache_key]

        client = self._get_client()
        if client is None:
            return []
        try:
            result = client.search(f"{title} film", limit=limit)
            self._cache[cache_key] = result.results
            return result.results
        except FirecrawlError as e:
            print(f"[Firecrawl] Поиск не удался для '{title}': {e}")
            return []
