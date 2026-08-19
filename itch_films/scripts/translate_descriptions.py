"""
scripts/translate_descriptions.py
──────────────────────────────────────────────────────────────────────
Переводит описания фильмов (film.description из Sakila) на русский
через OpenAI и сохраняет в локальный SQLite-файл
storage/film_descriptions_ru.db.

Использование (запуск из корня itch_films/):
    python scripts/translate_descriptions.py [опции]

Опции:
    --limit N       Максимум переводов за этот запуск (по умолчанию: без лимита,
                     переводит все непереведённые фильмы).
    --film-id ID    Перевести только один конкретный фильм.
    --dry-run       Показать, что было бы переведено; без вызовов API,
                     без записи в SQLite.

Примеры:
    # Посмотреть, сколько фильмов ещё не переведено (безопасный предпросмотр)
    python scripts/translate_descriptions.py --dry-run

    # Перевести один фильм
    python scripts/translate_descriptions.py --film-id 1

    # Перевести первые 20 непереведённых фильмов
    python scripts/translate_descriptions.py --limit 20

    # Перевести всё, что осталось (1001 фильм — пара минут, пара центов)
    python scripts/translate_descriptions.py

Правила безопасности:
    - Никогда не печатает API-ключ OpenAI.
    - Пропускает фильмы, у которых уже есть перевод в SQLite (не платит
      за повторный перевод одного и того же текста).
    - Хранилище — локальный SQLite-файл этого проекта, не общая с
      itch_films_OOP MySQL-таблица: переводы двух проектов независимы.
"""

import os
import sys
import argparse

# Принудительно UTF-8 на Windows (консоль по умолчанию — cp1252)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Настройка путей ────────────────────────────────────────────────────────
# scripts/translate_descriptions.py живёт внутри itch_films/, поэтому
# корень проекта — на один уровень выше (itch_films/).
_script_dir: str = os.path.dirname(os.path.abspath(__file__))
_itch_films: str = os.path.dirname(_script_dir)

if _itch_films in sys.path:
    sys.path.remove(_itch_films)
sys.path.insert(0, _itch_films)

from dotenv import load_dotenv
load_dotenv(os.path.join(_itch_films, '.env'))

# ── Импорты ───────────────────────────────────────────────────────────
import mysql.connector
import local_settings

from services.translations import (
    TranslationRepository,
    TranslationService,
    TranslationConfigurationError,
)

DB_PATH = os.path.join(_itch_films, 'storage', 'film_descriptions_ru.db')
LINE    = '=' * 52


# ── Разбор аргументов ──────────────────────────────────────────────────

def _positive_int(value: str) -> int:
    """Валидатор для argparse: целое число > 0."""
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid integer")
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer (got {n})")
    return n


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='ITCH Films — перевод описаний фильмов на русский (OpenAI)',
    )
    parser.add_argument(
        '--limit', type=_positive_int, default=None, metavar='N',
        help='Максимум переводов за этот запуск (по умолчанию: все непереведённые).',
    )
    parser.add_argument(
        '--film-id', type=_positive_int, default=None, dest='film_id', metavar='ID',
        help='Перевести только этот film_id (должно быть > 0).',
    )
    parser.add_argument(
        '--dry-run', action='store_true', dest='dry_run',
        help='Показать, что было бы переведено, без вызова OpenAI API и без записи.',
    )
    return parser.parse_args()


# ── Данные из Sakila (read-only) ────────────────────────────────────────

def _fetch_films_with_descriptions() -> list[dict]:
    """Все фильмы Sakila с непустым description."""
    conn = mysql.connector.connect(**local_settings.dbconfig)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT film_id, title, description
        FROM   film
        WHERE  description IS NOT NULL AND description != ''
        ORDER BY film_id
    """)
    films = cursor.fetchall()
    cursor.close()
    conn.close()
    return films


def _fetch_film_by_id(film_id: int) -> dict | None:
    conn = mysql.connector.connect(**local_settings.dbconfig)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT film_id, title, description FROM film WHERE film_id = %s",
        (film_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    repository = TranslationRepository(DB_PATH)

    if args.film_id is not None:
        film = _fetch_film_by_id(args.film_id)
        if film is None:
            print(f"\n[ОШИБКА] Film ID {args.film_id} не найден в Sakila.")
            sys.exit(1)
        candidates = [film] if film.get('description') else []
    else:
        already_translated = repository.get_translated_film_ids()
        all_films = _fetch_films_with_descriptions()
        candidates = [f for f in all_films if f['film_id'] not in already_translated]
        if args.limit is not None:
            candidates = candidates[:args.limit]

    print(LINE)
    print("  ITCH Films — перевод описаний фильмов (OpenAI)")
    print(f"  Хранилище : {DB_PATH}")
    print(f"  Уже переведено : {repository.count()}")
    print(f"  К переводу за этот запуск : {len(candidates)}")
    print(f"  Режим : {'DRY-RUN (без вызовов API)' if args.dry_run else 'БОЕВОЙ'}")
    print(LINE)

    if not candidates:
        print("\n  Переводить нечего.")
        return

    if args.dry_run:
        for film in candidates[:10]:
            print(f"\n  [{film['film_id']:>4}] {film['title']}")
            desc = film['description']
            print(f"        EN: {desc[:120]}{'...' if len(desc) > 120 else ''}")
        if len(candidates) > 10:
            print(f"\n  ... и ещё {len(candidates) - 10} фильмов.")
        print("\n  [DRY-RUN] Вызовов OpenAI API не было. Файл не изменялся.")
        return

    try:
        service = TranslationService()
    except TranslationConfigurationError as exc:
        print(f"\n[ОШИБКА КОНФИГУРАЦИИ] {exc}")
        print("  Добавь OPENAI_API_KEY в файл .env.")
        sys.exit(1)

    translated = 0
    failed = 0
    for film in candidates:
        try:
            description_ru = service.translate(film['description'])
            repository.save(film['film_id'], description_ru)
            translated += 1
            print(f"  [OK]     [{film['film_id']:>4}] {film['title'][:40]:<40}")
        except Exception as exc:
            failed += 1
            print(f"  [FAILED] [{film['film_id']:>4}] {film['title'][:40]:<40}  {exc}")

    print()
    print(LINE)
    print(f"  Переведено : {translated}")
    print(f"  Неудачно   : {failed}")
    print(f"  Всего в базе сейчас : {repository.count()}")
    print(LINE)


if __name__ == '__main__':
    main()
