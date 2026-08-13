import os
import sys
import logging

import mysql.connector

logger = logging.getLogger(__name__)

# Находим itch_films/local_settings.py от расположения этого файла:
#   __file__ → .../services/ai_images/poster_repository.py
#   dirname × 3 → Project_IT_Career_Hub_2/
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_itch_films = os.path.join(_project_root, 'itch_films')
if _itch_films not in sys.path:
    sys.path.insert(0, _itch_films)

import local_settings  # noqa: E402 — должно идти после настройки sys.path

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movie_posters (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    film_id     INT NOT NULL UNIQUE,
    title       VARCHAR(255) NOT NULL,
    genre       VARCHAR(100),
    description TEXT,
    prompt      TEXT,
    image_path  VARCHAR(500) NOT NULL,
    image_url   VARCHAR(500) NOT NULL,
    status      VARCHAR(50) DEFAULT 'generated',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def _get_write_conn():
    return mysql.connector.connect(**local_settings.dbconfig_write)


# ── DDL ───────────────────────────────────────────────────────────────

def create_movie_posters_table() -> None:
    """Создаёт movie_posters в write-базе данных, если она не существует."""
    conn = _get_write_conn()
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("Таблица movie_posters готова.")


# ── Чтение ──────────────────────────────────────────────────────────────

def get_poster_by_film_id(film_id: int) -> dict | None:
    """Возвращает запись постера для film_id, либо None, если не найдена."""
    conn = _get_write_conn()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM movie_posters WHERE film_id = %s", (film_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def poster_record_exists(film_id: int) -> bool:
    """Возвращает True, если запись постера для film_id уже существует."""
    conn = _get_write_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM movie_posters WHERE film_id = %s LIMIT 1", (film_id,)
    )
    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return exists


def get_poster_urls_by_ids(film_ids: list) -> dict:
    """
    Возвращает {film_id: image_url} для заданного списка ID фильмов.
    Используется Flask-приложением для обогащения результатов поиска URL постеров.
    При любой ошибке возвращает пустой словарь, чтобы сайт продолжал работать.
    """
    if not film_ids:
        return {}
    try:
        conn = _get_write_conn()
        cursor = conn.cursor()
        placeholders = ','.join(['%s'] * len(film_ids))
        cursor.execute(
            f"SELECT film_id, image_url FROM movie_posters WHERE film_id IN ({placeholders})",
            film_ids,
        )
        result = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        logger.warning(f"Не удалось получить URL постеров: {e}")
        return {}


# ── Запись ─────────────────────────────────────────────────────────────

def save_poster_record(
    film_id: int,
    title: str,
    genre: str,
    description: str,
    prompt: str,
    image_path: str,
    image_url: str,
    status: str = 'generated',
) -> None:
    """Вставляет новую запись постера в movie_posters."""
    conn = _get_write_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO movie_posters
            (film_id, title, genre, description, prompt, image_path, image_url, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (film_id, title, genre, description, prompt, image_path, image_url, status),
    )
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"Сохранена запись постера для film_id={film_id}")
