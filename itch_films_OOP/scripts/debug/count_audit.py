"""
scripts/debug/count_audit.py
Разовый диагностический скрипт (только чтение): считает фильмы в Sakila,
валидные OpenAI-постеры и файлы на диске, ищет расхождения между ними.

Это средний по подробности из трёх debug-скриптов проекта:
    - queue_status.py  — беглый взгляд (пара чисел, для быстрой проверки)
    - count_audit.py   — этот файл: сводный отчёт по всем таблицам сразу,
                          заканчивается конкретным списком "что осталось
                          сгенерировать"
    - audit_posters.py — построчный разбор конкретных проблемных записей,
                          когда сводки здесь недостаточно

Главный практический результат — секция "## Итог": сколько фильмов Sakila
ещё НЕ имеют валидного AI-постера. Это тот же список, что скормит себе
scripts/generate_movie_posters.py --target-from-db, поэтому удобно
прогнать этот скрипт перед батчем генерации, чтобы понимать масштаб
работы и заранее заметить расхождения (дубли, битые файлы), которые
могут исказить подсчёт.

Запуск из корня проекта:
    python scripts/debug/count_audit.py
"""

import os
import sys

# Скрипт лежит в itch_films_OOP/scripts/debug/, поэтому корень проекта —
# на два уровня выше (scripts/debug/ → scripts/ → корень).
_script_dir = os.path.dirname(os.path.abspath(__file__))
_itch_films = os.path.normpath(os.path.join(_script_dir, '..', '..'))

if _itch_films in sys.path:
    sys.path.remove(_itch_films)
sys.path.insert(0, _itch_films)

# Принудительно UTF-8 на Windows (консоль по умолчанию — cp1252,
# в неё не помещаются русские буквы из print() ниже).
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(_itch_films, '.env'))

import mysql.connector
import local_settings

STORAGE_DIR = os.path.join(_itch_films, 'storage', 'posters')
LINE = '=' * 60


def run():
    """
    Собирает и печатает отчёт о состоянии Sakila, movie_posters и файлов
    на диске.

    Структура: сначала три отдельных подключения к БД (Sakila read-only,
    write-база, снова write-база для файлов) собирают все нужные цифры
    в обычные переменные Python, и только в самом конце — единый блок
    print(), который форматирует уже готовые данные. Курсоры/соединения
    закрываются сразу после использования (а не держатся все функции) —
    чтобы не занимать соединения из пула дольше, чем нужно для разового
    диагностического запуска.
    """
    # ── 1. Подсчёты фильмов в Sakila (read-only, dbconfig) ────────────
    conn_r  = mysql.connector.connect(**local_settings.dbconfig)
    cur_r   = conn_r.cursor()

    cur_r.execute("SELECT COUNT(*) FROM film")
    total_films = cur_r.fetchone()[0]

    cur_r.execute("SELECT COUNT(DISTINCT film_id) FROM film")
    distinct_film_ids = cur_r.fetchone()[0]

    cur_r.execute("SELECT MIN(film_id), MAX(film_id) FROM film")
    min_id, max_id = cur_r.fetchone()

    # Sakila не гарантирует, что film_id идёт подряд без единого пропуска
    # (строки могли быть удалены). Чтобы дальше честно посчитать "какие
    # фильмы уже имеют постер", нужен ТОЧНЫЙ набор существующих id
    # (actual_set), а не просто диапазон min..max — иначе несуществующие
    # id тоже попали бы в список "надо сгенерировать".
    cur_r.execute("SELECT film_id FROM film ORDER BY film_id")
    all_sakila_ids = [row[0] for row in cur_r.fetchall()]
    expected_range = set(range(min_id, max_id + 1))
    actual_set     = set(all_sakila_ids)
    gaps           = sorted(expected_range - actual_set)

    cur_r.close()
    conn_r.close()

    # ── 2. Подсчёты movie_posters (write-база, dbconfig_write) ────────
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
        # "completed" в БД — это ещё не гарантия, что файл реально есть и
        # не пустой: запись могла остаться от старой генерации, а файл —
        # быть удалён вручную или перезаписан пустым при сбое. Поэтому
        # валидным считаем только то, что прошло ОБЕ проверки: запись
        # в БД + реальный файл на диске размером > 0 байт.
        valid_openai_ids = set()
        missing_files    = []
        for film_id, image_path in openai_rows:
            if image_path and os.path.isfile(image_path) and os.path.getsize(image_path) > 0:
                valid_openai_ids.add(film_id)
            else:
                missing_files.append((film_id, image_path))

        # Та же проверка "файл реально существует", но для ВСЕХ completed-
        # записей (не только provider='openai') — включает и mock-постеры.
        # Нужна отдельно от missing_files выше, потому что missing_files
        # смотрит только на openai, а тут — на любую завершённую запись.
        cur_w.execute(
            "SELECT film_id, image_path FROM movie_posters "
            "WHERE status = 'completed'"
        )
        all_completed_rows = cur_w.fetchall()
        db_missing_file = [
            (fid, ip) for fid, ip in all_completed_rows
            if not ip or not os.path.isfile(ip) or os.path.getsize(ip) == 0
        ]

        # Сколько элементов очереди генерации в каждом статусе — просто
        # для сводки в блоке вывода ниже (сама очередь подробно
        # разбирается в audit_posters.py, здесь только счётчики).
        try:
            cur_w.execute(
                "SELECT status, COUNT(*) FROM movie_generation_queue GROUP BY status"
            )
            queue_stats = dict(cur_w.fetchall())
        except Exception:
            queue_stats = {}

        # film_id в очереди, которых НЕТ в Sakila вообще — такого быть не
        # должно (очередь строится из списка фильмов Sakila), но если
        # кто-то руками добавил строку в movie_generation_queue с опечаткой
        # в film_id, эта проверка её найдёт.
        try:
            cur_w.execute("SELECT film_id FROM movie_generation_queue")
            queue_ids = {row[0] for row in cur_w.fetchall()}
            orphan_queue = sorted(queue_ids - actual_set)
        except Exception:
            orphan_queue = []

        # Сколько film_id имеют больше одной записи в movie_posters —
        # ожидаемо (история версий: mock → openai, повторные попытки
        # после сбоя), просто для масштаба картины в отчёте.
        cur_w.execute(
            "SELECT film_id, COUNT(*) AS cnt FROM movie_posters "
            "GROUP BY film_id HAVING cnt > 1"
        )
        duplicates = cur_w.fetchall()

    except mysql.connector.Error as e:
        # Если что-то из запросов выше упало (например, таблицы ещё не
        # созданы на свежей копии базы) — печатаем ошибку и выходим, а не
        # падаем трассировкой: это диагностический скрипт для человека,
        # а не часть сайта.
        print(f"[DB ERROR] {e}")
        cur_w.close()
        conn_w.close()
        return

    cur_w.close()
    conn_w.close()

    # ── 3. Файлы на диске (storage/posters/) ───────────────────────────
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

    # Файлы, которые физически лежат в storage/posters/, но ни одна строка
    # в movie_posters на них не ссылается — "мусор", оставшийся, например,
    # от прерванной генерации (файл записался, а INSERT в БД не прошёл).
    # Отдельное новое подключение к БД — специально для этой узкой сверки
    # путей, чтобы не тащить весь предыдущий курсор через блок файлов.
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

    # ── 4. Фильмы Sakila без валидной карточки (нужно сгенерировать) ───
    # Это и есть главный практический вывод скрипта: множество film_id из
    # Sakila МИНУС те, что уже имеют проверенный (файл существует и не
    # пустой) OpenAI-постер. Именно этот остаток нужно будет прогнать
    # через scripts/generate_movie_posters.py.
    needs_card = sorted(actual_set - valid_openai_ids)

    # ── Вывод отчёта ──────────────────────────────────────────────────
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
