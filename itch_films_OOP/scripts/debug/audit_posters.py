import os, sys, json
from collections import Counter, defaultdict

_itch_films = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _itch_films)

import mysql.connector
import local_settings

conn = mysql.connector.connect(**local_settings.dbconfig_write)
cur = conn.cursor(dictionary=True)

print("=== 1. movie_posters overview ===")
cur.execute("SELECT COUNT(*) AS n FROM movie_posters")
total = cur.fetchone()['n']
print("total records:", total)

cur.execute("SELECT COUNT(DISTINCT film_id) AS n FROM movie_posters")
unique_films = cur.fetchone()['n']
print("unique film_id:", unique_films)

cur.execute("""
    SELECT film_id, COUNT(*) AS cnt FROM movie_posters
    GROUP BY film_id HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""")
dupe_rows = cur.fetchall()
print("film_id with >1 record:", len(dupe_rows))
print("  top 10:", dupe_rows[:10])

cur.execute("SELECT provider, COUNT(*) AS n FROM movie_posters GROUP BY provider")
print("providers:", cur.fetchall())

cur.execute("SELECT status, COUNT(*) AS n FROM movie_posters GROUP BY status")
print("statuses:", cur.fetchall())

cur.execute("""
    SELECT film_id, COUNT(DISTINCT provider) AS providers
    FROM movie_posters GROUP BY film_id HAVING COUNT(DISTINCT provider) > 1
""")
multi_provider = cur.fetchall()
print("film_ids with multiple distinct providers:", len(multi_provider))
print("  sample:", multi_provider[:10])

# exact full-row duplicates (same film_id, provider, image_path)
cur.execute("""
    SELECT film_id, provider, image_path, COUNT(*) AS n
    FROM movie_posters
    GROUP BY film_id, provider, image_path
    HAVING COUNT(*) > 1
""")
exact_dupes = cur.fetchall()
print("exact duplicate (film_id+provider+image_path) groups:", len(exact_dupes))
print("  sample:", exact_dupes[:10])

print()
print("=== 2. Five mock films: all movie_posters records ===")
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
    # latest per get_latest_by_film_id logic (MAX id where status=completed)
    completed = [r for r in by_film.get(fid, []) if r['status'] == 'completed']
    latest = max(completed, key=lambda r: r['id']) if completed else None
    print("  => latest (completed, MAX id):", latest['id'] if latest else None,
          latest['provider'] if latest else None,
          os.path.basename(latest['image_path']) if latest else None)

print()
print("=== 3. WebP files on disk vs DB ===")
posters_dir = os.path.join(_itch_films, 'storage', 'posters')
disk_files = set(f for f in os.listdir(posters_dir) if f.lower().endswith('.webp'))
print("files on disk:", len(disk_files))

cur.execute("SELECT id, film_id, image_path FROM movie_posters")
all_rows = cur.fetchall()
db_filenames = defaultdict(list)
for r in all_rows:
    fn = os.path.basename(r['image_path'])
    db_filenames[fn].append(r)

db_filenames_set = set(db_filenames.keys())
orphan_files = disk_files - db_filenames_set
missing_files = db_filenames_set - disk_files

print("distinct filenames referenced in DB:", len(db_filenames_set))
print("orphan files (on disk, no DB record):", len(orphan_files))
print("  sample:", sorted(orphan_files)[:20])
print("DB records pointing to missing files:", len(missing_files))
print("  sample:", sorted(missing_files)[:20])
for fn in sorted(missing_files)[:20]:
    for r in db_filenames[fn]:
        print("   ", r)

print()
print("=== 4. Queue status ===")
cur.execute("SELECT status, COUNT(*) AS n FROM movie_generation_queue GROUP BY status")
queue_stats = cur.fetchall()
print("queue stats:", queue_stats)

cur.execute("SELECT COUNT(*) AS n FROM movie_generation_queue")
queue_total = cur.fetchone()['n']
print("queue total rows:", queue_total)

# films with completed openai poster but queue not done
cur.execute("SELECT DISTINCT film_id FROM movie_posters WHERE provider='openai' AND status='completed'")
openai_done_ids = set(r['film_id'] for r in cur.fetchall())
cur.execute("SELECT film_id, status FROM movie_generation_queue")
queue_map = {r['film_id']: r['status'] for r in cur.fetchall()}

mismatch_should_be_done = [fid for fid in openai_done_ids if queue_map.get(fid) != 'done']
print("has completed openai poster but queue status != done:", len(mismatch_should_be_done))
print("  sample:", mismatch_should_be_done[:20])

# queue done but no completed poster at all (any provider)
cur.execute("SELECT DISTINCT film_id FROM movie_posters WHERE status='completed'")
any_done_ids = set(r['film_id'] for r in cur.fetchall())
done_queue_ids = [fid for fid, st in queue_map.items() if st == 'done']
mismatch_done_no_poster = [fid for fid in done_queue_ids if fid not in any_done_ids]
print("queue status=done but NO completed poster record at all:", len(mismatch_done_no_poster))
print("  sample:", mismatch_done_no_poster[:20])

print()
print("=== 5. film_id=1 records ===")
cur.execute("SELECT id, film_id, provider, status, image_path, created_at FROM movie_posters WHERE film_id=1 ORDER BY id")
film1_rows = cur.fetchall()
for r in film1_rows:
    exists_on_disk = os.path.basename(r['image_path']) in disk_files
    print(" ", r, "| file_exists_on_disk:", exists_on_disk)

completed1 = [r for r in film1_rows if r['status']=='completed']
latest1 = max(completed1, key=lambda r: r['id']) if completed1 else None
print("=> latest served for film_id=1:", latest1['id'] if latest1 else None,
      os.path.basename(latest1['image_path']) if latest1 else None)

cur.close()
conn.close()
