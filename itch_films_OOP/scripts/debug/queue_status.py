"""Read-only queue status check. Run from project root."""
import sys, os
_script_dir = os.path.dirname(os.path.abspath(__file__))
_itch_films = os.path.normpath(os.path.join(_script_dir, '..', '..'))
sys.path.insert(0, _itch_films)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv(os.path.join(_itch_films, '.env'))
import mysql.connector, local_settings

conn = mysql.connector.connect(**local_settings.dbconfig_write)
cur  = conn.cursor()

cur.execute("SELECT status, COUNT(*) FROM movie_generation_queue GROUP BY status")
queue_rows = cur.fetchall()

cur.execute(
    "SELECT COUNT(DISTINCT film_id) FROM movie_posters "
    "WHERE provider='openai' AND status='completed'"
)
openai_done = cur.fetchone()[0]

cur.close(); conn.close()

print("Queue status:")
for status, cnt in sorted(queue_rows):
    print(f"  {status:<12}: {cnt}")
print(f"\nOpenAI completed posters: {openai_done}")