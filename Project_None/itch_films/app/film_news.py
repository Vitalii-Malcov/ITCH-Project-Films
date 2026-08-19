# ─────────────────────────────────────────────
# app/film_news.py
# Поиск дополнительной информации о фильме
# через Firecrawl. routes.py вызывает только
# get_film_news() и не знает деталей Firecrawl.
# ─────────────────────────────────────────────

# services/firecrawl/ — собственная копия клиента внутри itch_films,
# импортируется благодаря sys.path на корень itch_films/ из app/__init__.py.
from services.firecrawl import FirecrawlClient, FirecrawlError

# Клиент создаётся один раз при первом вызове get_film_news().
# None = ещё не инициализирован или инициализация не удалась.
_client = None


def _get_client():
    """Ленивая инициализация: создаём клиент только при первом обращении."""
    global _client
    if _client is None:
        try:
            _client = FirecrawlClient()
            print("[Firecrawl] Клиент инициализирован.")
        except Exception as e:
            print(f"[Firecrawl] Ошибка инициализации: {e}")
    return _client


def get_film_news(title: str, limit: int = 5) -> list:
    """
    Ищет дополнительную информацию о фильме через Firecrawl.

    Запрос "{title} film" возвращает Wikipedia, IMDb, Letterboxd —
    информационные страницы, а не только рецензии.

    Возвращает список словарей:
    [{"url": "...", "title": "...", "description": "..."}, ...]

    При любой ошибке возвращает [] — сайт продолжает работать.
    """
    client = _get_client()
    if client is None:
        return []

    try:
        result = client.search(f"{title} film", limit=limit)
        return result.results
    except FirecrawlError as e:
        print(f"[Firecrawl] Поиск не удался для '{title}': {e}")
        return []