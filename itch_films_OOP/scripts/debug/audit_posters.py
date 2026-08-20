"""
scripts/debug/audit_posters.py
Разовый диагностический скрипт (только чтение): подробный аудит таблицы
movie_posters — дубли записей, расхождения между БД и файлами на диске,
рассинхронизация с очередью генерации movie_generation_queue.

Это САМЫЙ подробный из трёх debug-скриптов проекта:
    - queue_status.py  — беглый взгляд на очередь (пара чисел)
    - count_audit.py   — сводка по всем таблицам сразу (счётчики + итог)
    - audit_posters.py — этот файл: построчный разбор конкретных проблемных
                          мест, с примерами реальных записей, а не только
                          цифрами

Используется, когда count_audit.py показал расхождение (например,
"Дублей film_id: 1001" или "DB-запись есть, файл отсутствует: N") и нужно
своими глазами посмотреть на конкретные строки в БД, чтобы понять причину.

Ничего не удаляет и не меняет — только печатает отчёт в консоль.

Запуск из корня проекта:
    python scripts/debug/audit_posters.py
"""

import os, sys, json
from collections import Counter, defaultdict

# Скрипт лежит в itch_films_OOP/scripts/debug/, поэтому корень проекта —
# на три уровня выше. Без этого `import local_settings` ниже не найдёт
# файл, если скрипт запущен не из корня проекта.
_itch_films = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _itch_films)

# Принудительно UTF-8 на Windows (консоль по умолчанию — cp1252,
# в неё не помещаются русские буквы из print() ниже).
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import mysql.connector
import local_settings

# movie_posters и movie_generation_queue живут в WRITE-базе (личная база
# студента, dbconfig_write) — это НЕ read-only Sakila. Сама Sakila (список
# фильмов) в этом скрипте не нужна, поэтому подключение только одно.
conn = mysql.connector.connect(**local_settings.dbconfig_write)
cur = conn.cursor(dictionary=True)

# ── 1. Общая картина по таблице movie_posters ──────────────────────────
# У одного фильма может быть НЕСКОЛЬКО записей в movie_posters — это не
# баг, а история версий: mock-заглушка, потом попытка через OpenAI, потом
# ещё одна попытка после ошибки и т.д. "Актуальный" постер сайт вычисляет
# как запись с MAX(id) среди status='completed' (см. PosterRepository.
# get_latest_by_film_id в services/ai_posters/poster_repository.py) —
# поэтому просто "записей больше, чем фильмов" — это ожидаемо, а не сигнал
# проблемы сам по себе.
print("=== 1. Обзор movie_posters ===")
cur.execute("SELECT COUNT(*) AS n FROM movie_posters")
total = cur.fetchone()['n']
print("всего записей:", total)

cur.execute("SELECT COUNT(DISTINCT film_id) AS n FROM movie_posters")
unique_films = cur.fetchone()['n']
print("уникальных film_id:", unique_films)

# Сколько именно фильмов имеют больше одной версии постера — просто для
# масштаба (если это почти все фильмы, значит генерация переигрывалась
# массово, а не для единичных проблемных случаев).
cur.execute("""
    SELECT film_id, COUNT(*) AS cnt FROM movie_posters
    GROUP BY film_id HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""")
dupe_rows = cur.fetchall()
print("film_id с более чем 1 записью:", len(dupe_rows))
print("  топ 10:", dupe_rows[:10])

# Разбивка по provider ('openai' — реальная генерация, 'mock' — заглушка
# без API) и по status ('completed'/'failed'/...) — быстрый взгляд, каким
# способом и с каким результатом создавались постеры.
cur.execute("SELECT provider, COUNT(*) AS n FROM movie_posters GROUP BY provider")
print("провайдеры:", cur.fetchall())

cur.execute("SELECT status, COUNT(*) AS n FROM movie_posters GROUP BY status")
print("статусы:", cur.fetchall())

# Фильмы, у которых пробовали ОБА провайдера — типичный случай: сначала
# сгенерировали mock-заглушку (например, для permanently blocked film_id
# из mock_blocked.py), потом позже всё же получилось через OpenAI.
cur.execute("""
    SELECT film_id, COUNT(DISTINCT provider) AS providers
    FROM movie_posters GROUP BY film_id HAVING COUNT(DISTINCT provider) > 1
""")
multi_provider = cur.fetchall()
print("film_id с несколькими разными провайдерами:", len(multi_provider))
print("  пример:", multi_provider[:10])

# А вот это уже настоящий подозрительный случай: одинаковые film_id +
# provider + image_path, повторённые больше одного раза. В отличие от
# обычной "истории версий" (разные id, разное время), тут ВСЁ совпадает —
# похоже на повторную вставку одной и той же генерации (например, скрипт
# генерации запускался дважды на одном и том же film_id без проверки
# poster_exists()).
cur.execute("""
    SELECT film_id, provider, image_path, COUNT(*) AS n
    FROM movie_posters
    GROUP BY film_id, provider, image_path
    HAVING COUNT(*) > 1
""")
exact_dupes = cur.fetchall()
print("групп точных дублей (film_id+provider+image_path):", len(exact_dupes))
print("  пример:", exact_dupes[:10])

print()
# ── 2. Пять фильмов, заблокированных модерацией OpenAI ─────────────────
# Это те же 5 film_id, что и BLOCKED_IDS в scripts/debug/mock_blocked.py —
# OpenAI отказывается их генерировать (moderation_blocked), поэтому для
# них есть mock-заглушки. Здесь печатаем ПОЛНУЮ историю записей по каждому
# из них и — отдельно — какую именно запись реально отдаст сайт (та же
# логика MAX(id) WHERE status='completed', что и в PosterRepository).
# Если тут окажется provider='openai' — значит блокировку сняли и мок уже
# не нужен; если всё ещё 'mock' — заглушка по-прежнему в деле.
print("=== 2. Пять mock-фильмов: все записи movie_posters ===")
mock_ids = [54, 153, 516, 680, 792]
placeholders = ','.join(['%s']*len(mock_ids))
cur.execute(f"""
    SELECT id, film_id, provider, model, status, image_path, created_at
    FROM movie_posters WHERE film_id IN ({placeholders})
    ORDER BY film_id, id
""", mock_ids)
rows = cur.fetchall()
by_film = defaultdict(list)
for r in rows:
    by_film[r['film_id']].append(r)
for fid in mock_ids:
    print(f"--- film_id={fid} ---")
    for r in by_film.get(fid, []):
        print(" ", r)
    # "Последняя" запись — по той же логике, что и get_latest_by_film_id
    # (MAX id среди записей со статусом completed). Именно её видит
    # пользователь на сайте прямо сейчас для этого film_id.
    completed = [r for r in by_film.get(fid, []) if r['status'] == 'completed']
    latest = max(completed, key=lambda r: r['id']) if completed else None
    print("  => последняя (completed, MAX id):", latest['id'] if latest else None,
          latest['provider'] if latest else None,
          os.path.basename(latest['image_path']) if latest else None)

print()
# ── 3. Сверка файлов на диске с записями в БД ───────────────────────────
# БД и файловая система — два независимых источника правды, которые
# должны совпадать, но могут разъехаться:
#   - "файл-сирота" — .webp лежит на диске, но ни одна запись в БД на
#     него не ссылается (например, вставка в БД упала ПОСЛЕ того, как
#     файл уже сохранился на диск — половина транзакции прошла);
#   - "запись без файла" — наоборот, в БД есть строка с image_path, но
#     самого файла на диске нет (например, файл удалили вручную или
#     storage/posters/ пересоздали не полностью).
# Оба случая ломают показ постера на сайте (PosterEnricher отдаст
# несуществующий путь) или просто засоряют диск лишними файлами.
print("=== 3. WebP-файлы на диске vs в БД ===")
posters_dir = os.path.join(_itch_films, 'storage', 'posters')
disk_files = set(f for f in os.listdir(posters_dir) if f.lower().endswith('.webp'))
print("файлов на диске:", len(disk_files))

cur.execute("SELECT id, film_id, image_path FROM movie_posters")
all_rows = cur.fetchall()
db_filenames = defaultdict(list)
for r in all_rows:
    fn = os.path.basename(r['image_path'])
    db_filenames[fn].append(r)

db_filenames_set = set(db_filenames.keys())
orphan_files = disk_files - db_filenames_set
missing_files = db_filenames_set - disk_files

print("уникальных имён файлов в БД:", len(db_filenames_set))
print("файлы-сироты (есть на диске, нет записи в БД):", len(orphan_files))
print("  пример:", sorted(orphan_files)[:20])
print("записей в БД, указывающих на отсутствующие файлы:", len(missing_files))
print("  пример:", sorted(missing_files)[:20])
# Для "пропавших" файлов печатаем ещё и саму запись из БД (film_id,
# provider, когда создана) — это подсказка, ЧТО именно потерялось и когда,
# а не просто голое имя файла.
for fn in sorted(missing_files)[:20]:
    for r in db_filenames[fn]:
        print("   ", r)

print()
# ── 4. Согласованность movie_generation_queue с реальными постерами ────
# movie_generation_queue — отдельная таблица-трекер: для каждого film_id
# она хранит, на каком этапе генерация постера (pending/processing/done/
# failed). Сама генерация (movie_posters) обновляется в одном месте кода,
# статус очереди — в другом (см. services/ai_posters/queue.py), поэтому
# теоретически они могут разъехаться, если один из шагов упадёт между
# обновлением очереди и сохранением постера (или наоборот).
print("=== 4. Статус очереди ===")
cur.execute("SELECT status, COUNT(*) AS n FROM movie_generation_queue GROUP BY status")
queue_stats = cur.fetchall()
print("статистика очереди:", queue_stats)

cur.execute("SELECT COUNT(*) AS n FROM movie_generation_queue")
queue_total = cur.fetchone()['n']
print("всего строк в очереди:", queue_total)

# Случай 1 (не страшно, но странно): постер от OpenAI реально готов
# (status='completed' в movie_posters), а очередь при этом НЕ отмечена
# как 'done'. Сайту это не мешает (он читает movie_posters напрямую), но
# сама очередь врёт о прогрессе — стоит знать, если полагаешься на неё
# для отчётности.
cur.execute("SELECT DISTINCT film_id FROM movie_posters WHERE provider='openai' AND status='completed'")
openai_done_ids = set(r['film_id'] for r in cur.fetchall())
cur.execute("SELECT film_id, status FROM movie_generation_queue")
queue_map = {r['film_id']: r['status'] for r in cur.fetchall()}

mismatch_should_be_done = [fid for fid in openai_done_ids if queue_map.get(fid) != 'done']
print("есть готовый постер openai, но статус очереди != done:", len(mismatch_should_be_done))
print("  пример:", mismatch_should_be_done[:20])

# Случай 2 (уже хуже): очередь говорит "done", но в movie_posters вообще
# НЕТ ни одной завершённой записи для этого film_id (даже mock). Это
# похоже на настоящий баг генерации: скрипт пометил элемент очереди
# готовым, но сама запись постера почему-то не сохранилась.
cur.execute("SELECT DISTINCT film_id FROM movie_posters WHERE status='completed'")
any_done_ids = set(r['film_id'] for r in cur.fetchall())
done_queue_ids = [fid for fid, st in queue_map.items() if st == 'done']
mismatch_done_no_poster = [fid for fid in done_queue_ids if fid not in any_done_ids]
print("статус очереди=done, но НЕТ ни одной готовой записи постера:", len(mismatch_done_no_poster))
print("  пример:", mismatch_done_no_poster[:20])

print()
# ── 5. Один конкретный фильм целиком (film_id=1) как контрольный пример ─
# film_id=1 — первый фильм в Sakila, обычный (не заблокированный) случай.
# Печатаем его историю целиком со статусом "есть ли файл на диске" по
# каждой строке — удобно для ручной проверки, что "последняя" запись
# действительно самая свежая и её файл реально существует, прежде чем
# доверять этой же логике по всей базе.
print("=== 5. Записи film_id=1 ===")
cur.execute("SELECT id, film_id, provider, status, image_path, created_at FROM movie_posters WHERE film_id=1 ORDER BY id")
film1_rows = cur.fetchall()
for r in film1_rows:
    exists_on_disk = os.path.basename(r['image_path']) in disk_files
    print(" ", r, "| файл_есть_на_диске:", exists_on_disk)

completed1 = [r for r in film1_rows if r['status']=='completed']
latest1 = max(completed1, key=lambda r: r['id']) if completed1 else None
print("=> последний, который отдаётся для film_id=1:", latest1['id'] if latest1 else None,
      os.path.basename(latest1['image_path']) if latest1 else None)

cur.close()
conn.close()
