"""
TranslationRepository — CRUD-интерфейс для переводов описаний фильмов.

Хранилище — локальный SQLite-файл (storage/film_descriptions_ru.db),
НЕ удалённая MySQL-база movie_posters. Это намеренное архитектурное
решение: movie_posters общая между itch_films и itch_films_OOP (и это
уже один раз вызвало баг — тестовая запись в одном проекте перекрыла
"актуальный" постер в обоих), а переводы описаний должны быть у
каждого проекта полностью свои, без общей инфраструктуры вообще.

sqlite3 — часть стандартной библиотеки Python, новых зависимостей
устанавливать не нужно.
"""

import sqlite3
from datetime import datetime, timezone


class TranslationRepository:
    """CRUD-интерфейс для таблицы descriptions в локальном SQLite-файле."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._ensure_schema()

    # ── Подключение и схема ──────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_schema(self) -> None:
        """Создаёт таблицу, если её ещё нет. Безопасно вызывать многократно."""
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS descriptions (
                    film_id        INTEGER PRIMARY KEY,
                    description_ru TEXT NOT NULL,
                    created_at     TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # ── Чтение ────────────────────────────────────────────────────────────

    def get_many(self, film_ids: list[int]) -> dict[int, str]:
        """
        Возвращает {film_id: description_ru} для всех переданных film_id,
        у которых есть перевод. Один SQL-запрос на весь список — тот же
        принцип, что у PosterRepository.get_latest_by_film_ids(): не
        ходить в базу по одному разу на фильм.
        """
        if not film_ids:
            return {}
        conn = self._connect()
        try:
            placeholders = ",".join("?" * len(film_ids))
            cursor = conn.execute(
                f"SELECT film_id, description_ru FROM descriptions "
                f"WHERE film_id IN ({placeholders})",
                film_ids,
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_translated_film_ids(self) -> set[int]:
        """Все film_id, для которых перевод уже есть — используется CLI-скриптом,
        чтобы не переводить одно и то же повторно."""
        conn = self._connect()
        try:
            cursor = conn.execute("SELECT film_id FROM descriptions")
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM descriptions")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    # ── Запись ────────────────────────────────────────────────────────────

    def save(self, film_id: int, description_ru: str) -> None:
        """
        Сохраняет перевод. INSERT OR REPLACE — в отличие от movie_posters,
        здесь версионирование не нужно: перевод либо есть, либо его нет,
        предыдущая версия для истории не интересна.
        """
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO descriptions (film_id, description_ru, created_at) "
                "VALUES (?, ?, ?)",
                (film_id, description_ru, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
