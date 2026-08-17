"""
scripts/debug/count_audit.py
Read-only audit: counts films in Sakila, valid OpenAI posters, disk files.
Run from project root:
    python scripts/debug/count_audit.py
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

STORAGE_DIR = os.path.join(_itch_films, 'storage', 'posters')
LINE = '=' * 60


def run():
    # ── 1. Sakila film counts ──────────────────────────────────────
    conn_r  = mysql.connector.connect(**local_settings.dbconfig)
    cur_r   = conn_r.cursor()

    cur_r.execute("SELECT COUNT(*) FROM film")
    total_films = cur_r.fetchone()[0]

    cur_r.execute("SELECT COUNT(DISTINCT film_id) FROM film")
    distinct_film_ids = cur_r.fetchone()[0]

    cur_r.execute("SELECT MIN(film_id), MAX(film_id) FROM film")
    min_id, max_id = cur_r.fetchone()

    # Check gaps in sequence
    cur_r.execute("SELECT film_id FROM film ORDER BY film_id")
    all_sakila_ids = [row[0] for row in cur_r.fetchall()]
    expected_range = set(range(min_id, max_id + 1))
    actual_set     = set(all_sakila_ids)
    gaps           = sorted(expected_range - actual_set)

    cur_r.close()
    conn_r.close()

    # ── 2. movie_posters counts ────────────────────────────────────
    conn_w = mysql.connector.connect(**local_settings.dbconfig_write)
    cur_w  = conn_w.cursor()

    try:
        cur_w.execute("SELECT COUNT(*) FROM movie_posters")
        total_poster_records = cur_w.fetchone()[0]

        cur_w.execute("SELECT COUNT(DISTINCT film_id) FROM movie_posters")
        distinct_poster_film_ids = cur_w.fetchone()[0]

        cur_w.execute(
            "SELECT COUNT(DISTINCT film_id) FROM movie_posters "
            "WHERE provider = 'openai' AND status = 'completed'"
        )
        openai_completed = cur_w.fetchone()[0]

        cur_w.execute(
            "SELECT film_id, image_path FROM movie_posters "
            "WHERE provider = 'openai' AND status = 'completed'"
        )
        openai_rows = cur_w.fetchall()
        # Build set of film_ids with VALID file on disk
        valid_openai_ids = set()
        missing_files    = []
        for film_id, image_path in openai_rows:
            if image_path and os.path.isfile(image_path) and os.path.getsize(image_path) > 0:
                valid_openai_ids.add(film_id)
            else:
                missing_files.append((film_id, image_path))

        # Records in movie_posters whose file is missing
        cur_w.execute(
            "SELECT film_id, image_path FROM movie_posters "
            "WHERE status = 'completed'"
        )
        all_completed_rows = cur_w.fetchall()
        db_missing_file = [
            (fid, ip) for fid, ip in all_completed_rows
            if not ip or not os.path.isfile(ip) or os.path.getsize(ip) == 0
        ]

        # queue stats
        try:
            cur_w.execute(
                "SELECT status, COUNT(*) FROM movie_generation_queue GROUP BY status"
            )
            queue_stats = dict(cur_w.fetchall())
        except Exception:
            queue_stats = {}

        # film_ids in queue not in Sakila
        try:
            cur_w.execute("SELECT film_id FROM movie_generation_queue")
            queue_ids = {row[0] for row in cur_w.fetchall()}
            orphan_queue = sorted(queue_ids - actual_set)
        except Exception:
            orphan_queue = []

        # duplicate film_ids in movie_posters
        cur_w.execute(
            "SELECT film_id, COUNT(*) AS cnt FROM movie_posters "
            "GROUP BY film_id HAVING cnt > 1"
        )
        duplicates = cur_w.fetchall()

    except mysql.connector.Error as e:
        print(f"[DB ERROR] {e}")
        cur_w.close()
        conn_w.close()
        return

    cur_w.close()
    conn_w.close()

    # ── 3. Disk files ──────────────────────────────────────────────
    if os.path.isdir(STORAGE_DIR):
        all_disk_files = [
            f for f in os.listdir(STORAGE_DIR)
            if f.endswith('.webp')
        ]
        disk_count = len(all_disk_files)
        disk_full_paths = {
            os.path.join(STORAGE_DIR, f) for f in all_disk_files
        }
    else:
        disk_count = 0
        disk_full_paths = set()

    # Files on disk without a DB record
    cur_w2 = None
    orphan_files = []
    try:
        conn_w2 = mysql.connector.connect(**local_settings.dbconfig_write)
        cur_w2  = conn_w2.cursor()
        cur_w2.execute("SELECT image_path FROM movie_posters")
        db_paths = {row[0] for row in cur_w2.fetchall() if row[0]}
        orphan_files = sorted(disk_full_paths - db_paths)
        cur_w2.close()
        conn_w2.close()
    except Exception:
        pass

    # ── 4. Missing Sakila films (need a card) ──────────────────────
    needs_card = sorted(actual_set - valid_openai_ids)

    # ── Output ────────────────────────────────────────────────────
    print(LINE)
    print("  ITCH Films — Audit Report (read-only)")
    print(LINE)

    print("\n## База Sakila")
    print(f"  Всего строк в film             : {total_films}")
    print(f"  Уникальных film_id             : {distinct_film_ids}")
    print(f"  Минимальный film_id            : {min_id}")
    print(f"  Максимальный film_id           : {max_id}")
    print(f"  Ожидаемый диапазон             : {min_id}–{max_id}  ({max_id - min_id + 1} позиций)")
    print(f"  Пропусков в последовательности : {len(gaps)}")
    if gaps:
        shown = gaps[:20]
        print(f"    Первые пропуски: {shown}" + (" ..." if len(gaps) > 20 else ""))

    print("\n## movie_posters")
    print(f"  Всего записей                  : {total_poster_records}")
    print(f"  Уникальных film_id             : {distinct_poster_film_ids}")
    print(f"  Записей OpenAI (completed)     : {openai_completed}")
    print(f"  Валидных OpenAI-карточек       : {len(valid_openai_ids)}  (файл есть и > 0 байт)")
    print(f"  Дублей film_id                 : {len(duplicates)}")
    if duplicates:
        for fid, cnt in duplicates[:10]:
            print(f"    film_id={fid}  ({cnt} записей)")

    print("\n## Файлы на диске")
    print(f"  .webp файлов в storage/posters : {disk_count}")
    print(f"  Файлов без записи в movie_posters: {len(orphan_files)}")

    print("\n## Проверка целостности")
    print(f"  DB-запись есть, файл отсутствует: {len(db_missing_file)}")
    if db_missing_file[:5]:
        for fid, ip in db_missing_file[:5]:
            print(f"    film_id={fid}  path={ip}")
    print(f"  OpenAI-запись есть, файл отсутствует: {len(missing_files)}")
    if missing_files[:5]:
        for fid, ip in missing_files[:5]:
            print(f"    film_id={fid}  path={ip}")

    print("\n## Очередь movie_generation_queue")
    for status in ('pending', 'processing', 'done', 'failed'):
        cnt = queue_stats.get(status, 0)
        print(f"  {status:<12} : {cnt}")
    print(f"  Orphan в очереди (нет в Sakila): {len(orphan_queue)}")
    if orphan_queue:
        print(f"    {orphan_queue[:10]}")

    print("\n## Итог")
    print(f"  Фильмов в Sakila               : {distinct_film_ids}")
    print(f"  Валидных AI-карточек (OpenAI)  : {len(valid_openai_ids)}")
    print(f"  Осталось сгенерировать         : {len(needs_card)}")

    print(LINE)

    if needs_card:
        show = needs_card[:20]
        print(f"  Первые film_id без карточки : {show}" + (" ..." if len(needs_card) > 20 else ""))
    else:
        print("  Все фильмы Sakila уже имеют валидные AI-карточки!")
    print(LINE)


if __name__ == '__main__':
    run()