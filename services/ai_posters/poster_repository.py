"""
PosterRepository — database abstraction for the movie_posters table.

Responsibilities:
    - Create and manage the movie_posters table in the write database.
    - Save new poster records after successful generation.
    - Read poster records for the Flask app (by film_id or list of ids).

What it does NOT do:
    - Generate images or build prompts.
    - Know about file paths beyond what it stores.
    - Know about Flask or HTTP.

Repository Pattern:
    PosterService and Flask routes depend on PosterRepository, not on raw
    MySQL calls. Swapping the database engine means changing only this file.

URL derivation:
    The table stores image_path (absolute path on disk).
    image_url (/posters/000001.webp) is computed from os.path.basename —
    no redundant column, no sync issues.
"""

import os
import sys
import logging

import mysql.connector
from mysql.connector.connection import MySQLConnection

from services.ai_posters.exceptions import RepositoryError

logger = logging.getLogger(__name__)

# ── sys.path: locate itch_films/local_settings.py ────────────────────
# __file__ → .../services/ai_posters/poster_repository.py
# dirname × 3 → Project_IT_Career_Hub_2/
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_itch_films = os.path.join(_project_root, 'itch_films')
if _itch_films not in sys.path:
    sys.path.insert(0, _itch_films)

import local_settings  # noqa: E402

# ── DDL ──────────────────────────────────────────────────────────────
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movie_posters (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    film_id         INT NOT NULL,
    provider        VARCHAR(50)  NOT NULL,
    model           VARCHAR(100),
    prompt          TEXT         NOT NULL,
    negative_prompt TEXT,
    style           VARCHAR(50),
    seed            BIGINT,
    width           INT,
    height          INT,
    image_path      VARCHAR(500) NOT NULL,
    status          VARCHAR(50)  DEFAULT 'completed',
    generation_time FLOAT,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_film_id (film_id),
    INDEX idx_status  (status)
)
"""


class PosterRepository:
    """CRUD interface for the movie_posters table in the write database."""

    # ── Connection ────────────────────────────────────────────────────

    def _connect(self) -> MySQLConnection:
        """Open and return a connection to the write database."""
        try:
            return mysql.connector.connect(**local_settings.dbconfig_write)
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Cannot connect to write database.",
                details=str(exc),
            ) from exc

    # ── DDL ───────────────────────────────────────────────────────────

    def create_table(self) -> None:
        """Create movie_posters table if it does not exist."""
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(_CREATE_TABLE_SQL)
            conn.commit()
            logger.info("movie_posters table is ready.")
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Failed to create movie_posters table.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    # ── Read ──────────────────────────────────────────────────────────

    def poster_exists(self, film_id: int) -> bool:
        """
        Return True if at least one completed poster exists for film_id.
        Used by PosterService before generating to skip already-done films.
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM movie_posters "
                "WHERE film_id = %s AND status = 'completed' LIMIT 1",
                (film_id,),
            )
            return cursor.fetchone() is not None
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"poster_exists query failed for film_id={film_id}.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def get_completed_film_ids(self) -> set[int]:
        """
        Return a set of all film_ids that have at least one completed poster.

        Used by the generation script to build the queue efficiently:
        one query instead of 1001 individual poster_exists() calls.
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT DISTINCT film_id FROM movie_posters "
                "WHERE status = 'completed'"
            )
            return {row[0] for row in cursor.fetchall()}
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "get_completed_film_ids failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def openai_poster_exists(self, film_id: int) -> bool:
        """
        Return True if at least one completed OpenAI poster exists for film_id.

        Differs from poster_exists(): only considers provider='openai'.
        Mock posters (provider='mock') are intentionally excluded so that
        films with mock placeholders can still be re-generated with OpenAI.
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM movie_posters "
                "WHERE film_id = %s AND provider = 'openai' "
                "AND status = 'completed' LIMIT 1",
                (film_id,),
            )
            return cursor.fetchone() is not None
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"openai_poster_exists query failed for film_id={film_id}.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def get_openai_completed_film_ids(self) -> set[int]:
        """
        Return film_ids that have at least one completed OpenAI poster.

        Used by the generation script to build the queue without re-enqueueing
        films that already have a real OpenAI poster. Mock posters are excluded.
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT DISTINCT film_id FROM movie_posters "
                "WHERE provider = 'openai' AND status = 'completed'"
            )
            return {row[0] for row in cursor.fetchall()}
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "get_openai_completed_film_ids failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def get_latest_by_film_id(self, film_id: int) -> dict | None:
        """
        Return the most recently generated poster for one film, or None.
        'Latest' is determined by MAX(id) — avoids created_at ties.
        """
        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT mp.*
                FROM   movie_posters mp
                WHERE  mp.id = (
                    SELECT MAX(id) FROM movie_posters
                    WHERE film_id = %s AND status = 'completed'
                )
                """,
                (film_id,),
            )
            row = cursor.fetchone()
            return self._add_url(row) if row else None
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"get_latest_by_film_id failed for film_id={film_id}.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def get_latest_by_film_ids(self, film_ids: list[int]) -> dict[int, dict]:
        """
        Return the latest completed poster for each film_id in the list.

        Uses a single JOIN query — one DB round-trip regardless of list size.
        This is the primary method called by Flask to enrich search results.

        Returns:
            {film_id: poster_record_dict}
            Films without a poster are absent from the result.
        """
        if not film_ids:
            return {}

        placeholders = ', '.join(['%s'] * len(film_ids))
        sql = f"""
            SELECT mp.*
            FROM   movie_posters mp
            INNER JOIN (
                SELECT film_id, MAX(id) AS max_id
                FROM   movie_posters
                WHERE  film_id IN ({placeholders})
                AND    status = 'completed'
                GROUP  BY film_id
            ) latest ON mp.id = latest.max_id
        """
        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, film_ids)
            rows = cursor.fetchall()
            return {row['film_id']: self._add_url(row) for row in rows}
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "get_latest_by_film_ids failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    # ── Write ─────────────────────────────────────────────────────────

    def save(
        self,
        film_id: int,
        provider: str,
        model: str,
        prompt: str,
        negative_prompt: str,
        style: str,
        seed: int | None,
        width: int,
        height: int,
        image_path: str,
        status: str,
        generation_time: float,
    ) -> int:
        """
        Insert a new poster record and return its auto-generated id.

        Multiple records per film_id are allowed — each represents a version.
        The latest version is always retrieved via MAX(id).
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO movie_posters
                    (film_id, provider, model, prompt, negative_prompt,
                     style, seed, width, height, image_path,
                     status, generation_time)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    film_id, provider, model, prompt, negative_prompt,
                    style, seed, width, height, image_path,
                    status, generation_time,
                ),
            )
            conn.commit()
            poster_id = cursor.lastrowid
            logger.info(
                f"Saved poster record id={poster_id} "
                f"film_id={film_id} provider={provider}"
            )
            return poster_id
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"Failed to save poster record for film_id={film_id}.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _add_url(row: dict) -> dict:
        """
        Compute image_url from image_path and add it to the record dict.

        Stored:  image_path = '/abs/path/storage/posters/000001.webp'
        Derived: image_url  = '/posters/000001.webp'

        Keeping only image_path in the DB avoids data duplication.
        If the URL scheme changes, only this method needs updating.
        """
        filename = os.path.basename(row.get('image_path', ''))
        row['image_url'] = f"/posters/{filename}" if filename else ''
        return row