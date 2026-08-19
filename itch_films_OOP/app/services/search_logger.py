# ─────────────────────────────────────────────
# app/services/search_logger.py
# Логирование поисков в MongoDB.
#
# routes.py вызывает только search_logger.log_search() и не знает
# деталей подключения или структуры документа.
#
# ВАЖНО: MongoDB никогда не ломает сайт. Если подключение недоступно —
# log_search() молча возвращает None, сайт продолжает работать.
# ─────────────────────────────────────────────

from datetime import datetime

from app.services.mongo_connection import MongoConnection


class SearchLogger:
    """Пишет один документ в MongoDB на каждый выполненный поиск."""

    def __init__(self, connection: MongoConnection):
        self._connection = connection

    def log_search(self, search_type: str, search_value: str = "", genre: str = "",
                    year_from: str = "", year_to: str = "", results_count: int = 0):
        """
        Записывает один поисковый запрос.

        Возвращает inserted_id при успехе, None — если MongoDB
        недоступна или запись не удалась (сайт не должен падать
        из-за недоступности логирования).
        """
        collection = self._connection.collection
        if collection is None:
            print("[MongoDB] Лог пропущен — нет подключения.")
            return None

        try:
            log_entry = {
                "timestamp":     datetime.now(),
                "search_type":   search_type,
                "search_value":  search_value,
                "genre":         genre,
                "year_from":     year_from,
                "year_to":       year_to,
                "results_count": results_count,
            }
            result = collection.insert_one(log_entry)
            return result.inserted_id
        except Exception as e:
            print(f"[MongoDB] Ошибка записи: {e}")
            return None

    def delete_all(self) -> int:
        """
        Удаляет все записи логов (кнопка "Сбросить статистику").

        Возвращает количество удалённых документов, 0 — если MongoDB
        недоступна или коллекция уже пуста.
        """
        collection = self._connection.collection
        if collection is None:
            print("[MongoDB] Сброс пропущен — нет подключения.")
            return 0

        try:
            result = collection.delete_many({})
            return result.deleted_count
        except Exception as e:
            print(f"[MongoDB] Ошибка сброса статистики: {e}")
            return 0
