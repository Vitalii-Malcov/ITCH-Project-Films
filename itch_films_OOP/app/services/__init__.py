# ─────────────────────────────────────────────
# app/services/__init__.py
# Сервисный слой приложения (MongoDB, Firecrawl, подмешивание постеров).
#
# Не путать с корневым services/ (services/ai_posters, services/firecrawl) —
# тот пакет живёт на уровень выше и переиспользуется CLI-скриптами;
# этот app/services/ — только для веб-слоя ITCH Films.
# ─────────────────────────────────────────────

from app.services.mongo_connection import MongoConnection
from app.services.search_logger import SearchLogger
from app.services.search_stats import SearchStatsRepository
from app.services.film_news_service import FilmNewsService
from app.services.poster_enricher import PosterEnricher

__all__ = [
    "MongoConnection",
    "SearchLogger",
    "SearchStatsRepository",
    "FilmNewsService",
    "PosterEnricher",
]
