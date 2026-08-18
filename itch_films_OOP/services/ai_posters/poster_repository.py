"""
PosterRepository — абстракция базы данных для таблицы movie_posters.

Обязанности:
    - Создавать и обслуживать таблицу movie_posters в write-базе данных.
    - Сохранять новые записи постеров после успешной генерации.
    - Читать записи постеров для Flask-приложения (по film_id или списку id).

Чего НЕ делает:
    - Не генерирует изображения и не строит промпты.
    - Не знает про пути к файлам сверх того, что хранит.
    - Не знает про Flask или HTTP.

Паттерн Repository:
    PosterService и Flask-маршруты зависят от PosterRepository, а не от сырых
    вызовов MySQL. Смена движка БД означает изменение только этого файла.

Вычисление URL:
    Таблица хранит image_path (абсолютный путь на диске).
    image_url (/posters/000001.webp) вычисляется из os.path.basename —
    без избыточной колонки, без проблем рассинхронизации.
"""

import os
import sys
import logging

import mysql.connector
from mysql.connector.connection import MySQLConnection

from services.ai_posters.exceptions import RepositoryError

logger = logging.getLogger(__name__)

# ── sys.path: находим itch_films_OOP/local_settings.py ────────────────
# __file__ → .../itch_films_OOP/services/ai_posters/poster_repository.py
# dirname × 3 → itch_films_OOP/ (корень проекта).
_itch_films = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _itch_films in sys.path:
    sys.path.remove(_itch_films)
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
    """CRUD-интерфейс для таблицы movie_posters в write-базе данных."""

    # ── Подключение ────────────────────────────────────────────────────

    def _connect(self) -> MySQLConnection:
        """
        Возвращает подключение к write-базе данных — из пула (pool_name),
        а не новое TCP-соединение на каждый вызов. См. подробный комментарий
        в app/repositories/film_repository.py:_get_connection() — тот же приём.
        """
        try:
            return mysql.connector.connect(
                pool_name="itch_films_write",
                pool_size=5,
                **local_settings.dbconfig_write,
            )
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Cannot connect to write database.",
                details=str(exc),
            ) from exc

    # ── DDL ───────────────────────────────────────────────────────────

    def create_table(self) -> None:
        """Создаёт таблицу movie_posters, если она не существует."""
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(_CREATE_TABLE_SQL)
            conn.commit()
            logger.info("Таблица movie_posters готова.")
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Failed to create movie_posters table.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    # ── Чтение ──────────────────────────────────────────────────────────

    def poster_exists(self, film_id: int) -> bool:
        """
        Возвращает True, если для film_id существует хотя бы один завершённый постер.
        Используется PosterService перед генерацией, чтобы пропускать уже готовые фильмы.
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
        Возвращает множество всех film_id, у которых есть хотя бы один
        завершённый постер.

        Используется скриптом генерации для эффективного построения очереди:
        один запрос вместо 1001 отдельного вызова poster_exists().
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
        Возвращает True, если для film_id существует хотя бы один завершённый
        постер от OpenAI.

        Отличие от poster_exists(): учитывает только provider='openai'.
        Mock-постеры (provider='mock') намеренно исключены, чтобы фильмы
        с mock-плейсхолдерами можно было по-прежнему перегенерировать через OpenAI.
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
        Возвращает film_id, у которых есть хотя бы один завершённый постер от OpenAI.

        Используется скриптом генерации, чтобы не ставить в очередь повторно
        фильмы, у которых уже есть настоящий постер от OpenAI. Mock-постеры исключены.
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
        Возвращает самый недавно сгенерированный постер для одного фильма, либо None.
        «Актуальный» определяется через MAX(id) — избегает конфликтов по created_at.
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
        Возвращает последний завершённый постер для каждого film_id из списка.

        Использует один JOIN-запрос — один round-trip к БД независимо от размера списка.
        Это основной метод, который вызывает Flask для обогащения результатов поиска.

        Возвращает:
            {film_id: словарь_записи_постера}
            Фильмы без постера отсутствуют в результате.
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

    # ── Запись ─────────────────────────────────────────────────────────

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
        Вставляет новую запись постера и возвращает её автоматически
        сгенерированный id.

        Допускается несколько записей на один film_id — каждая представляет
        версию. Актуальная версия всегда извлекается через MAX(id).
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
                f"Сохранена запись постера id={poster_id} "
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

    # ── Приватные вспомогательные методы ───────────────────────────────────────

    @staticmethod
    def _add_url(row: dict) -> dict:
        """
        Вычисляет image_url из image_path и добавляет его в словарь записи.

        Хранится:    image_path = '/abs/path/storage/posters/000001.webp'
        Вычисляется: image_url  = '/posters/000001.webp'

        Хранение только image_path в БД избегает дублирования данных.
        При изменении схемы URL нужно обновить только этот метод.
        """
        filename = os.path.basename(row.get('image_path', ''))
        row['image_url'] = f"/posters/{filename}" if filename else ''
        return row
