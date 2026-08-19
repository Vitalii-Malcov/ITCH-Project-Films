# ─────────────────────────────────────────────
# app/services/search_stats.py
# Чтение статистики поисков из MongoDB (страница /stats).
#
# Этот класс только ЧИТАЕТ документы, записанные SearchLogger'ом.
# Если MongoDB недоступна — методы возвращают пустой список / 0
# и печатают сообщение в терминал, а не бросают исключение.
# ─────────────────────────────────────────────

from pymongo import DESCENDING

from app.services.mongo_connection import MongoConnection


class SearchStatsRepository:
    """Агрегирует и читает статистику поисков из коллекции search_logs."""

    def __init__(self, connection: MongoConnection):
        self._connection = connection

    def get_popular_searches(self, limit: int = 5) -> list[dict]:
        """
        Топ-N самых популярных запросов через Aggregation Pipeline:
        $match (без пустых) → $group (считаем count и last_seen) → $sort → $limit.
        Сортировка: сначала по count (убывание), при равном count —
        по last_seen (сначала более новый), а не в случайном порядке MongoDB.
        Возвращает [{"_id": "alien", "count": 7, "last_seen": datetime(...)}, ...].
        """
        collection = self._connection.collection
        if collection is None:
            print("[MongoDB Stats] Нет подключения — популярные запросы недоступны.")
            return []
        try:
            pipeline = [
                {"$match": {"search_value": {"$ne": ""}}},
                {"$group": {
                    "_id":       "$search_value",
                    "count":     {"$sum": 1},
                    "last_seen": {"$max": "$timestamp"},
                }},
                {"$sort": {"count": -1, "last_seen": -1}},
                {"$limit": limit},
            ]
            return list(collection.aggregate(pipeline))
        except Exception as e:
            print(f"[MongoDB Stats] Ошибка get_popular_searches: {e}")
            return []

    def get_recent_searches(self, limit: int = 5) -> list[dict]:
        """N последних поисков — сортировка по timestamp по убыванию."""
        collection = self._connection.collection
        if collection is None:
            print("[MongoDB Stats] Нет подключения — последние запросы недоступны.")
            return []
        try:
            return list(collection.find().sort("timestamp", DESCENDING).limit(limit))
        except Exception as e:
            print(f"[MongoDB Stats] Ошибка get_recent_searches: {e}")
            return []

    def get_total_searches(self) -> int:
        """Общее количество документов в коллекции (все поиски)."""
        collection = self._connection.collection
        if collection is None:
            return 0
        try:
            return collection.count_documents({})
        except Exception as e:
            print(f"[MongoDB Stats] Ошибка get_total_searches: {e}")
            return 0

    def get_unique_queries(self) -> int:
        """Количество уникальных поисковых запросов (разных search_value)."""
        collection = self._connection.collection
        if collection is None:
            return 0
        try:
            pipeline = [
                {"$match": {"search_value": {"$ne": ""}}},
                {"$group": {"_id": "$search_value"}},
                {"$count": "total"},
            ]
            result = list(collection.aggregate(pipeline))
            return result[0]["total"] if result else 0
        except Exception as e:
            print(f"[MongoDB Stats] Ошибка get_unique_queries: {e}")
            return 0

    def get_all_searches(self, limit: int = 10, offset: int = 0) -> list[dict]:
        """Все поисковые запросы постранично, новые первыми."""
        collection = self._connection.collection
        if collection is None:
            return []
        try:
            return list(
                collection.find()
                .sort("timestamp", DESCENDING)
                .skip(offset)
                .limit(limit)
            )
        except Exception as e:
            print(f"[MongoDB Stats] Ошибка get_all_searches: {e}")
            return []

    def get_unique_searches(self, limit: int = 10, offset: int = 0) -> list[dict]:
        """
        Уникальные запросы постранично через агрегацию: группируем по
        search_value (count = сколько раз искали, last_seen = последний
        раз), сортируем по частоте, применяем пагинацию.
        """
        collection = self._connection.collection
        if collection is None:
            return []
        try:
            pipeline = [
                {"$match": {"search_value": {"$ne": ""}}},
                {"$group": {
                    "_id":       "$search_value",
                    "count":     {"$sum": 1},
                    "last_seen": {"$max": "$timestamp"},
                }},
                {"$sort":  {"count": -1}},
                {"$skip":  offset},
                {"$limit": limit},
            ]
            return list(collection.aggregate(pipeline))
        except Exception as e:
            print(f"[MongoDB Stats] Ошибка get_unique_searches: {e}")
            return []
