"""
scripts/debug/mock_blocked.py
Generate mock posters for the 5 permanently safety-blocked films.

These films cannot be generated via OpenAI (moderation_blocked).
MockProvider creates a solid-color WebP based on genre — no API calls.

Run from project root:
    python scripts/debug/mock_blocked.py
"""

import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_itch_films = os.path.normpath(os.path.join(_script_dir, '..', '..'))

if _itch_films in sys.path:
    sys.path.remove(_itch_films)
sys.path.insert(0, _itch_films)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(_itch_films, '.env'))

import mysql.connector
import local_settings

from services.ai_posters import (
    MockProvider, PosterStorage, PosterRepository, PosterService,
)

STORAGE_DIR = os.path.join(_itch_films, 'storage', 'posters')

# The 5 films permanently blocked by OpenAI safety system
BLOCKED_IDS = [54, 153, 516, 680, 792]

LINE = '=' * 52


def fetch_film(film_id: int) -> dict | None:
    conn   = mysql.connector.connect(**local_settings.dbconfig)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT   f.film_id, f.title, f.description,
                 MIN(c.name) AS genre
        FROM     film f
        LEFT JOIN film_category fc ON f.film_id      = fc.film_id
        LEFT JOIN category      c  ON fc.category_id = c.category_id
        WHERE    f.film_id = %s
        GROUP BY f.film_id, f.title, f.description
    """, (film_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def main():
    print(LINE)
    print("  Mock poster generator — 5 safety-blocked films")
    print("  Provider: MockProvider (solid-color WebP, no API)")
    print(LINE)

    service = PosterService(
        provider   = MockProvider(),
        storage    = PosterStorage(STORAGE_DIR),
        repository = PosterRepository(),
    )

    generated = 0
    for film_id in BLOCKED_IDS:
        film = fetch_film(film_id)
        if not film:
            print(f"  [SKIP] film_id={film_id} not found in Sakila")
            continue

        desc = (film.get('description') or '').strip()
        if not desc:
            desc = f"{film['title']}. A {film.get('genre') or 'Drama'} film."

        print(f"\n  [{film_id}] {film['title']}  (genre: {film.get('genre') or 'N/A'})")
        try:
            poster_id = service.generate(
                film_id     = film['film_id'],
                title       = film['title'],
                genre       = film.get('genre') or '',
                description = desc,
            )
            url = service.get_poster_url(film['film_id'])
            print(f"       poster_id={poster_id}  url={url}")
            generated += 1
        except Exception as exc:
            print(f"       [ERROR] {exc}")

    print()
    print(LINE)
    print(f"  Generated : {generated} / {len(BLOCKED_IDS)}")
    print(f"  Provider  : mock (no OpenAI API calls, no cost)")
    print(LINE)


if __name__ == '__main__':
    main()