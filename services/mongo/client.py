import os
import logging
from dataclasses import asdict
from datetime import datetime, timezone

from pymongo import MongoClient

from services.firecrawl import FirecrawlResult, CrawlResult, SearchResult

logger = logging.getLogger(__name__)


class MongoService:
    """Service for storing and retrieving Firecrawl results in MongoDB."""

    def __init__(self):
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        db_name = os.getenv("MONGO_DB_NAME", "it_career_hub")
        self._client = MongoClient(uri)
        self._db = self._client[db_name]
        logger.info(f"MongoService connected to '{db_name}'")

    # ------------------------------------------------------------------
    # Save methods
    # ------------------------------------------------------------------

    def save_scrape(self, result: FirecrawlResult) -> str:
        """Save a FirecrawlResult to the 'scrapes' collection."""
        doc = asdict(result)
        doc["saved_at"] = datetime.now(timezone.utc)
        inserted = self._db.scrapes.insert_one(doc)
        logger.info(f"Saved scrape: {result.url}")
        return str(inserted.inserted_id)

    def save_search(self, result: SearchResult) -> str:
        """Save a SearchResult to the 'searches' collection."""
        doc = result.to_dict()
        doc["saved_at"] = datetime.now(timezone.utc)
        inserted = self._db.searches.insert_one(doc)
        logger.info(f"Saved search: '{result.query}'")
        return str(inserted.inserted_id)

    def save_crawl(self, result: CrawlResult) -> str:
        """Save a CrawlResult to the 'crawls' collection."""
        doc = result.to_dict()
        doc["saved_at"] = datetime.now(timezone.utc)
        inserted = self._db.crawls.insert_one(doc)
        logger.info(f"Saved crawl: {result.url}, pages={result.total}")
        return str(inserted.inserted_id)

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_recent(self, collection: str, limit: int = 10) -> list:
        """Return the most recent documents from any collection."""
        cursor = self._db[collection].find(
            {},
            {"_id": 0}               # exclude ObjectId — not JSON-serializable
        ).sort("saved_at", -1).limit(limit)
        return list(cursor)