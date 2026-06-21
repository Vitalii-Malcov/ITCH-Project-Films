# ─────────────────────────────────────────────
# app/mongo_logger.py
# Логирование поисков в MongoDB.
#
# Этот файл берёт на себя ВСЮ работу с MongoDB.
# routes.py вызывает только log_search() и не
# знает деталей подключения или структуры данных.
#
# ВАЖНО: MongoDB никогда не ломает сайт.
# Если подключение недоступно — выводим сообщение
# в терминал и продолжаем работу без логирования.
# ─────────────────────────────────────────────

from pymongo import MongoClient
from datetime import datetime
import local_settings

# Модульная переменная: коллекция MongoDB.
# None означает "нет соединения" — все функции
# проверяют это перед работой с базой.
_collection = None


def _connect():
    """
    Приватная функция подключения к MongoDB.
    Вызывается один раз при импорте модуля.
    serverSelectionTimeoutMS=2000 — ждём не более
    2 секунд, чтобы не тормозить запуск сервера.
    """
    global _collection
    try:
        client = MongoClient(
            local_settings.MONGO_URI,
            serverSelectionTimeoutMS=2000  # таймаут 2 сек
        )
        # Проверяем реальное соединение — без этой строки
        # MongoClient не выдаёт ошибку сразу при создании.
        client.server_info()

        db = client[local_settings.MONGO_DATABASE]
        _collection = db["search_logs"]
        print("[MongoDB] Подключение успешно.")

    except Exception as e:
        print(f"[MongoDB] Ошибка подключения: {e}")
        print("[MongoDB] Логирование отключено. Сайт работает без MongoDB.")
        _collection = None


def log_search(search_type, search_value="", genre="",
               year_from="", year_to="", results_count=0):
    """
    Записывает один поисковый запрос в MongoDB.

    Параметры:
        search_type   — тип поиска: "title", "genre", "year"
        search_value  — строка запроса пользователя
        genre         — выбранный жанр (если есть)
        year_from     — год от (если есть)
        year_to       — год до (если есть)
        results_count — количество найденных фильмов

    Возвращает:
        inserted_id — если запись успешна
        None        — если MongoDB недоступна или ошибка
    """
    # Если нет подключения — молча пропускаем, не ломаем сайт.
    if _collection is None:
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
        result = _collection.insert_one(log_entry)
        return result.inserted_id

    except Exception as e:
        print(f"[MongoDB] Ошибка записи: {e}")
        return None


# ── Запускаем подключение при импорте модуля ───
_connect()