# ─────────────────────────────────────────────
# app/services/mongo_connection.py
# Тонкая обёртка над одним подключением к MongoDB.
#
# И SearchLogger (пишет поиски), и SearchStatsRepository (читает
# статистику) получают готовый MongoConnection через конструктор
# (dependency injection) вместо того, чтобы каждый лез в pymongo сам.
# ─────────────────────────────────────────────

import logging
import sys

from pymongo import MongoClient
from pymongo.collection import Collection

# "database" — MongoDB тоже база данных (см. logging_setup.py:
# logs/database.log собирает и MySQL, и MongoDB).
logger = logging.getLogger("database")

# Некоторые консоли Windows используют однобайтовую кодировку (например
# cp1252), в которую не помещаются русские буквы из print() ниже. Без
# этой настройки такой print() крашится с UnicodeEncodeError и роняет
# запуск всего сервера. errors="replace" вместо падения просто
# заменяет нечитаемые символы на "?".
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(errors="replace")
        except Exception:
            pass


class MongoConnection:
    """
    Подключается к одной коллекции MongoDB при создании объекта.

    label используется только в терминальных сообщениях — чтобы было
    видно, какое именно подключение (для записи логов или для чтения
    статистики) не удалось, если MongoDB недоступна.
    """

    def __init__(self, uri: str, database: str, collection: str, label: str = "MongoDB"):
        self._label = label
        self._collection: Collection | None = None
        self._connect(uri, database, collection)

    def _connect(self, uri: str, database: str, collection: str) -> None:
        client = None
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            # Принудительная проверка — MongoClient не бросает исключение
            # при создании, только при первом реальном запросе.
            client.server_info()
            self._collection = client[database][collection]
            print(f"[{self._label}] Подключение успешно.")
        except Exception as e:
            # MongoClient мог успеть запустить фоновые потоки мониторинга
            # ещё до того, как server_info() упал — если не закрыть его
            # явно, эти потоки/сокеты останутся висеть без дела.
            if client is not None:
                client.close()
            logger.exception("[%s] Ошибка подключения к MongoDB", self._label)
            print(f"[{self._label}] Ошибка подключения: {e}")
            print(f"[{self._label}] Сайт продолжит работать без MongoDB.")
            self._collection = None

    @property
    def collection(self) -> Collection | None:
        """None означает «нет подключения» — вызывающий код обязан это проверять."""
        return self._collection

    @property
    def is_connected(self) -> bool:
        return self._collection is not None
