# ─────────────────────────────────────────────
# app/services/poster_enricher.py
# Подмешивает image_url в список фильмов из write-БД movie_posters.
#
# Использует уже-ООП PosterRepository (services/ai_posters/) — этот
# класс просто оркестрирует один вызов на всю страницу результатов
# вместо N отдельных запросов по одному на фильм.
# ─────────────────────────────────────────────

import logging

logger = logging.getLogger(__name__)


class PosterEnricher:
    """Добавляет movie["image_url"] к каждому фильму в списке, на месте."""

    def __init__(self, default_poster: str, poster_repository=None):
        """
        poster_repository передаётся через конструктор (dependency
        injection), а не создаётся внутри enrich() на каждый вызов —
        так же, как остальные сервисы этого пакета получают свои
        зависимости. По умолчанию None: реальный PosterRepository
        создаётся один раз здесь же — импорт внутри __init__, а не на
        уровне модуля, чтобы не тянуть services.ai_posters (и его
        зависимости от БД) при простом импорте app.services.
        """
        self._default_poster = default_poster
        if poster_repository is None:
            from services.ai_posters import PosterRepository
            poster_repository = PosterRepository()
        self._poster_repository = poster_repository

    def enrich(self, movies: list[dict]) -> None:
        """
        Один JOIN-запрос на всю страницу результатов через
        PosterRepository.get_latest_by_film_ids() вместо отдельного
        запроса на каждый фильм. При недоступности таблицы movie_posters
        (например, БД ещё не создана) — все фильмы получают
        default_poster, ошибка не пробрасывается наверх.
        """
        try:
            film_ids = [movie["film_id"] for movie in movies]
            posters  = self._poster_repository.get_latest_by_film_ids(film_ids)
        except Exception:
            logger.exception("PosterEnricher: не удалось получить постеры для %d фильмов", len(movies))
            posters = {}

        for movie in movies:
            record = posters.get(movie["film_id"])
            movie["image_url"] = record["image_url"] if record else self._default_poster
