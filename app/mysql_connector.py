# ─────────────────────────────────────────────
# app/mysql_connector.py
# Подключение к MySQL и все SQL-запросы.
# Routes не пишут SQL — они вызывают функции
# из этого файла. Один файл — одна задача.
# ─────────────────────────────────────────────

import sys
import os

# Добавляем корень проекта в sys.path.
# Это нужно чтобы найти local_settings.py при двух сценариях:
#
#   1. python app/mysql_connector.py   ← Python видит только папку app/
#   2. python run.py                   ← Python видит корень, всё работает само
#
# __file__  =  .../itch_films/app/mysql_connector.py
# dirname(__file__)        →  .../itch_films/app/
# dirname(dirname(__file__))  →  .../itch_films/       ← нам нужно сюда
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import mysql.connector   # библиотека для работы с MySQL
import local_settings    # наши настройки подключения (itch_films/local_settings.py)


def get_connection():
    """Создаёт и возвращает подключение к базе данных Sakila (чтение)."""
    # **local_settings.dbconfig "распаковывает" словарь в аргументы функции.
    # Это то же самое что написать:
    #   host="ich-db...", user="ich1", password="...", database="sakila"
    # Но короче и удобнее — настройки хранятся в одном месте.
    connection = mysql.connector.connect(**local_settings.dbconfig)
    return connection


def test_connection():
    """
    Проверяет подключение к Sakila.
    Выполняет один SELECT и печатает результат в терминал.
    Используется только для проверки на Этапе 2.
    """
    try:
        # Открываем соединение с базой данных
        conn = get_connection()

        # Курсор — это инструмент для выполнения SQL-запросов.
        # Представь его как "указатель" внутри базы данных.
        cursor = conn.cursor()

        # Выполняем тестовый запрос: берём первые 5 фильмов
        cursor.execute("SELECT film_id, title, release_year FROM film LIMIT 5")

        # fetchall() забирает все строки результата в список
        films = cursor.fetchall()

        print("=" * 45)
        print("  Подключение к Sakila: УСПЕХ")
        print("=" * 45)
        print("  Первые 5 фильмов из базы:")
        print("-" * 45)

        # Перебираем строки результата.
        # Каждая строка — это кортеж (film_id, title, release_year)
        for film in films:
            film_id, title, year = film
            print(f"  [{film_id}] {title} ({year})")

        print("=" * 45)

        # Важно закрывать курсор и соединение после работы.
        # Иначе MySQL будет держать лишние открытые соединения.
        cursor.close()
        conn.close()

    except mysql.connector.Error as error:
        # Если подключение не удалось — выводим понятное сообщение
        print("=" * 45)
        print(f"  Ошибка подключения к MySQL:")
        print(f"  {error}")
        print("  Проверь local_settings.py")
        print("=" * 45)


def get_all_genres():
    """
    Возвращает список всех жанров из таблицы category.
    Используется для фильтра по жанру на странице поиска.

    Возвращает список словарей:
    [{"id": 1, "name": "Action"}, {"id": 2, "name": "Comedy"}, ...]
    """
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT category_id, name FROM category ORDER BY name")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    # Превращаем список кортежей в список словарей.
    # Словарь удобнее: в шаблоне пишем genre["name"]
    # вместо genre[1].
    genres = [{"id": row[0], "name": row[1]} for row in rows]
    return genres


def get_year_range():
    """
    Возвращает минимальный и максимальный год выпуска фильмов.
    Используется чтобы задать границы слайдера лет на странице поиска.

    Возвращает словарь:
    {"min_year": 2006, "max_year": 2006}
    """
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT MIN(release_year), MAX(release_year) FROM film")
    row = cursor.fetchone()   # fetchone() — берём только одну строку результата

    cursor.close()
    conn.close()

    return {"min_year": int(row[0]), "max_year": int(row[1])}


def search_movies_by_title(keyword, limit=10, offset=0):
    """
    Ищет фильмы по части названия (регистр не важен).
    Возвращает максимум 10 фильмов за один запрос.

    Аргументы:
      keyword  — строка поиска, например "ace" или "love"
      limit    — максимум результатов (по умолчанию 10)
      offset   — сколько строк пропустить (для будущей пагинации)

    Возвращает список словарей:
    [{"film_id": 2, "title": "ACE GOLDFINGER", "year": 2006, ...}, ...]

    ВАЖНО: используем %s вместо f-строк в SQL.
    f-строки в SQL опасны — это SQL-инъекция.
    %s — это параметризованный запрос, MySQL сам экранирует данные.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # LIKE %keyword% означает: найди title, который содержит
    # keyword в любом месте — в начале, середине или конце.
    # Пример: keyword="ace" найдёт "ACE GOLDFINGER", "SPACE JELLY" и т.д.
    search_pattern = f"%{keyword}%"

    # LEFT JOIN добавляет жанр к каждому фильму.
    # Проблема без GROUP BY: если у фильма несколько жанров в film_category,
    # JOIN даёт несколько строк — один фильм появляется несколько раз.
    # Решение: GROUP BY film_id схлопывает все строки одного фильма в одну.
    # MIN(c.name) выбирает один жанр (алфавитно первый) из всех жанров фильма.
    query = """
        SELECT f.film_id, f.title, f.release_year, f.rating, f.length,
               MIN(c.name) AS genre
        FROM   film f
        LEFT JOIN film_category fc ON f.film_id      = fc.film_id
        LEFT JOIN category      c  ON fc.category_id = c.category_id
        WHERE  f.title LIKE %s
        GROUP BY f.film_id, f.title, f.release_year, f.rating, f.length
        ORDER  BY f.title
        LIMIT  %s OFFSET %s
    """

    cursor.execute(query, (search_pattern, limit, offset))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    movies = [
        {
            "film_id": row[0],
            "title":   row[1],
            "year":    int(row[2]) if row[2] else None,
            "rating":  row[3],
            "length":  row[4],
            "genre":   row[5],   # новое поле — название жанра или None
        }
        for row in rows
    ]
    return movies


def search_movies_by_genre(genre_name, limit=10, offset=0):
    """
    Ищет фильмы по точному названию жанра.
    Возвращает максимум 10 фильмов.

    Аргументы:
      genre_name — точное название, например "Action" или "Comedy"
      limit      — максимум результатов (по умолчанию 10)
      offset     — для будущей пагинации

    Возвращает список словарей с теми же полями что search_movies_by_title().

    ЭТАП 5: здесь можно добавить year_from/year_to как доп. WHERE-условия.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # INNER JOIN (без LEFT) — нам нужны только фильмы с конкретным жанром.
    # c.name = %s — точное совпадение (не LIKE), регистр важен.
    query = """
        SELECT f.film_id, f.title, f.release_year, f.rating, f.length,
               c.name AS genre
        FROM   film f
        JOIN   film_category fc ON f.film_id      = fc.film_id
        JOIN   category      c  ON fc.category_id = c.category_id
        WHERE  c.name = %s
        ORDER  BY f.title
        LIMIT  %s OFFSET %s
    """

    cursor.execute(query, (genre_name, limit, offset))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    movies = [
        {
            "film_id": row[0],
            "title":   row[1],
            "year":    int(row[2]) if row[2] else None,
            "rating":  row[3],
            "length":  row[4],
            "genre":   row[5],
        }
        for row in rows
    ]
    return movies


# Этот блок запускается только если выполнить файл напрямую:
#   python app/mysql_connector.py
# При импорте модуля (from app import mysql_connector)
# этот блок НЕ выполняется.
if __name__ == "__main__":
    # ── Тест 1: подключение ────────────────────
    test_connection()

    # ── Тест 2: жанры ──────────────────────────
    print("\n  Жанры из Sakila:")
    print("-" * 45)
    genres = get_all_genres()
    for genre in genres:
        print(f"  [{genre['id']}] {genre['name']}")

    # ── Тест 3: диапазон лет ───────────────────
    years = get_year_range()
    print(f"\n  Годы выпуска: {years['min_year']} – {years['max_year']}")

    # ── Тест 4: поиск по названию ──────────────
    print("\n  Поиск фильмов по слову 'love':")
    print("-" * 45)
    results = search_movies_by_title("love")
    for movie in results:
        print(f"  {movie['title']} ({movie['year']}) | {movie['rating']} | {movie['length']} мин")