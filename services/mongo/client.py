import os
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from pymongo import MongoClient

from services.firecrawl import FirecrawlResult, CrawlResult, SearchResult

logger = logging.getLogger(__name__)


class MongoService:
    """Сервис для сохранения и чтения результатов Firecrawl в MongoDB."""

    def __init__(self):
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        db_name = os.getenv("MONGO_DB_NAME", "it_career_hub")
        self._client = MongoClient(uri)
        self._db = self._client[db_name]
        logger.info(f"MongoService connected to '{db_name}'")

    # ------------------------------------------------------------------
    # Методы сохранения
    # ------------------------------------------------------------------

    def save_scrape(self, result: FirecrawlResult) -> str:
        """Сохраняет FirecrawlResult в коллекцию 'scrapes'."""
        doc = asdict(result)
        doc["saved_at"] = datetime.now(timezone.utc)
        inserted = self._db.scrapes.insert_one(doc)
        logger.info(f"Saved scrape: {result.url}")
        return str(inserted.inserted_id)

    def save_search(self, result: SearchResult) -> str:
        """Сохраняет SearchResult в коллекцию 'searches'."""
        doc = result.to_dict()
        doc["saved_at"] = datetime.now(timezone.utc)
        inserted = self._db.searches.insert_one(doc)
        logger.info(f"Saved search: '{result.query}'")
        return str(inserted.inserted_id)

    def save_crawl(self, result: CrawlResult) -> str:
        """Сохраняет CrawlResult в коллекцию 'crawls'."""
        doc = result.to_dict()
        doc["saved_at"] = datetime.now(timezone.utc)
        inserted = self._db.crawls.insert_one(doc)
        logger.info(f"Saved crawl: {result.url}, pages={result.total}")
        return str(inserted.inserted_id)

    # ------------------------------------------------------------------
    # Методы чтения
    # ------------------------------------------------------------------

    def get_recent(self, collection: str, limit: int = 10) -> list:
        """Возвращает самые недавние документы из любой коллекции."""
        cursor = self._db[collection].find(
            {},
            {"_id": 0}               # исключаем ObjectId — не сериализуется в JSON
        ).sort("saved_at", -1).limit(limit)
        return list(cursor)