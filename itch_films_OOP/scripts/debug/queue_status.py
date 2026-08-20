"""
scripts/debug/queue_status.py
Разовая проверка статуса очереди генерации (только чтение).

Это самый простой из трёх debug-скриптов проекта — беглый взгляд в пару
чисел, без подробностей (см. count_audit.py для полной сводки по всем
таблицам и audit_posters.py для построчного разбора конкретных проблем).
Удобно запускать прямо во время долгого прогона
scripts/generate_movie_posters.py в соседнем терминале, чтобы одним
взглядом понять, сколько уже сделано и сколько осталось, не открывая БД
вручную через MySQL-клиент.

Запуск из корня проекта:
    python scripts/debug/queue_status.py
"""
import sys, os

# Скрипт лежит в itch_films_OOP/scripts/debug/, поэтому корень проекта —
# на два уровня выше (scripts/debug/ → scripts/ → корень). Нужен для
# import local_settings ниже.
_script_dir = os.path.dirname(os.path.abspath(__file__))
_itch_films = os.path.normpath(os.path.join(_script_dir, '..', '..'))
sys.path.insert(0, _itch_films)

# Принудительно UTF-8 на Windows (консоль по умолчанию — cp1252,
# в неё не помещаются русские буквы из print() ниже).
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(_itch_films, '.env'))
import mysql.connector, local_settings

# movie_generation_queue и movie_posters живут в WRITE-базе (личная база
# студента) — это не read-only Sakila, поэтому dbconfig_write.
conn = mysql.connector.connect(**local_settings.dbconfig_write)
cur  = conn.cursor()

# Сколько элементов очереди в каждом статусе — pending (ждёт своей
# очереди), processing (генерируется прямо сейчас), done (готово),
# failed (сорвалось, например moderation_blocked или сетевая ошибка).
# Именно эти четыре статуса и печатаются ниже.
cur.execute("SELECT status, COUNT(*) FROM movie_generation_queue GROUP BY status")
queue_rows = cur.fetchall()

# Отдельная проверка "по факту": сколько фильмов реально имеют завершённый
# (completed) постер именно от OpenAI в movie_posters — не то же самое,
# что "done" в очереди выше (очередь и таблица постеров обновляются
# разными частями кода и в теории могут разойтись; здесь просто берём
# число из первоисточника, а не из очереди, для быстрой сверки на глаз).
cur.execute(
    "SELECT COUNT(DISTINCT film_id) FROM movie_posters "
    "WHERE provider='openai' AND status='completed'"
)
openai_done = cur.fetchone()[0]

cur.close(); conn.close()

print("Статус очереди:")
# sorted() тут сортирует кортежи (status, count) по первому элементу —
# то есть по алфавиту статуса (done, failed, pending, processing), просто
# для стабильного порядка вывода при каждом запуске.
for status, cnt in sorted(queue_rows):
    print(f"  {status:<12}: {cnt}")
print(f"\nГотовых постеров OpenAI: {openai_done}")
