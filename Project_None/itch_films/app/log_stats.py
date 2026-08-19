# ─────────────────────────────────────────────
# app/log_stats.py
# Чтение статистики поисков из MongoDB.
#
# Этот файл только ЧИТАЕТ данные из коллекции
# search_logs. Запись ведёт mongo_logger.py.
# Используется на странице /stats.
#
# Если MongoDB недоступна — функции возвращают
# пустой список и выводят сообщение в терминал.
# ─────────────────────────────────────────────

from pymongo import MongoClient, DESCENDING
import local_settings

# Модульная переменная: коллекция MongoDB.
# None означает "нет соединения".
_collection = None


def _connect():
    """
    Приватная функция подключения к MongoDB.
    Вызывается один раз при импорте модуля.
    """
    global _collection
    try:
        client = MongoClient(
            local_settings.MONGO_URI,
            serverSelectionTimeoutMS=2000  # ждём не более 2 секунд
        )
        # Принудительная проверка — MongoClient не бросает
        # исключение при создании, только при первом запросе.
        client.server_info()

        db = client[local_settings.MONGO_DATABASE]
        _collection = db[local_settings.MONGO_COLLECTION]
        print("[MongoDB Stats] Подключение успешно.")

    except Exception as e:
        print(f"[MongoDB Stats] Ошибка подключения: {e}")
        print("[MongoDB Stats] Статистика недоступна. Сайт работает без MongoDB.")
        _collection = None


def get_popular_searches(limit=5):
    """
    Возвращает топ-N самых популярных поисковых запросов.

    Использует MongoDB Aggregation Pipeline:
      1. $match  — исключаем пустые строки запроса
      2. $group  — группируем одинаковые search_value,
                   считаем количество вхождений (count)
      3. $sort   — сортируем по count по убыванию
      4. $limit  — оставляем только первые N записей

    Возвращает список словарей вида:
        [{"_id": "alien", "count": 7}, ...]

    При ошибке — возвращает пустой список [].
    """
    if _collection is None:
        print("[MongoDB Stats] Нет подключения — популярные запросы недоступны.")
        return []

    try:
        pipeline = [
            # Шаг 1: берём только записи с непустым search_value
            {"$match": {"search_value": {"$ne": ""}}},

            # Шаг 2: группируем по search_value, считаем количество
            {"$group": {
                "_id":   "$search_value",
                "count": {"$sum": 1}
            }},

            # Шаг 3: сортируем — самые популярные первыми
            {"$sort": {"count": -1}},

            # Шаг 4: берём только топ-N
            {"$limit": limit}
        ]

        results = list(_collection.aggregate(pipeline))
        return results

    except Exception as e:
        print(f"[MongoDB Stats] Ошибка get_popular_searches: {e}")
        return []


def get_recent_searches(limit=5):
    """
    Возвращает N последних поисковых запросов.

    Сортирует коллекцию по полю timestamp по убыванию
    (самые новые — первыми) и берёт первые N записей.

    Возвращает список словарей из MongoDB (с полем _id).

    При ошибке — возвращает пустой список [].
    """
    if _collection is None:
        print("[MongoDB Stats] Нет подключения — последние запросы недоступны.")
        return []

    try:
        results = list(
            _collection
            .find()
            .sort("timestamp", DESCENDING)  # новые первыми
            .limit(limit)
        )
        return results

    except Exception as e:
        print(f"[MongoDB Stats] Ошибка get_recent_searches: {e}")
        return []


def get_total_searches():
    """Общее количество документов в коллекции (все поиски)."""
    if _collection is None:
        return 0
    try:
        return _collection.count_documents({})
    except Exception as e:
        print(f"[MongoDB Stats] Ошибка get_total_searches: {e}")
        return 0


def get_unique_queries():
    """Количество уникальных поисковых запросов (разных search_value)."""
    if _collection is None:
        return 0
    try:
        pipeline = [
            {"$match": {"search_value": {"$ne": ""}}},
            {"$group": {"_id": "$search_value"}},
            {"$count": "total"}
        ]
        result = list(_collection.aggregate(pipeline))
        return result[0]["total"] if result else 0
    except Exception as e:
        print(f"[MongoDB Stats] Ошибка get_unique_queries: {e}")
        return 0


def get_all_searches(limit=10, offset=0):
    """
    Возвращает все поисковые запросы постранично, новые первыми.

    Аргументы:
      limit  — записей на страницу (по умолчанию 10)
      offset — сколько записей пропустить (для пагинации)

    Возвращает список документов MongoDB.
    При ошибке или недоступности — возвращает [].
    """
    if _collection is None:
        return []
    try:
        results = list(
            _collection
            .find()
            .sort("timestamp", DESCENDING)  # новые первыми
            .skip(offset)
            .limit(limit)
        )
        return results
    except Exception as e:
        print(f"[MongoDB Stats] Ошибка get_all_searches: {e}")
        return []


def get_unique_searches(limit=10, offset=0):
    """
    Возвращает уникальные запросы постранично через агрегацию.

    Pipeline:
      1. $match  — исключаем пустые search_value
      2. $group  — группируем по search_value:
                   count = количество поисков,
                   last_seen = максимальный timestamp
      3. $sort   — самые частые первыми (count убыв.)
      4. $skip   — пропускаем offset записей
      5. $limit  — берём limit записей

    Возвращает список вида:
      [{"_id": "alien", "count": 7, "last_seen": datetime}, ...]

    При ошибке или недоступности — возвращает [].
    """
    if _collection is None:
        return []
    try:
        pipeline = [
            {"$match": {"search_value": {"$ne": ""}}},
            {"$group": {
                "_id":      "$search_value",
                "count":    {"$sum": 1},
                "last_seen": {"$max": "$timestamp"}
            }},
            {"$sort":  {"count": -1}},
            {"$skip":  offset},
            {"$limit": limit}
        ]
        return list(_collection.aggregate(pipeline))
    except Exception as e:
        print(f"[MongoDB Stats] Ошибка get_unique_searches: {e}")
        return []


# ── Запускаем подключение при импорте модуля ───
_connect()