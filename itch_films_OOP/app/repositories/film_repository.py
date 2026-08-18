# ─────────────────────────────────────────────
# app/repositories/film_repository.py
# Repository pattern: вся работа с MySQL (Sakila) спрятана
# внутри класса FilmRepository. routes.py больше не пишет
# SQL и не открывает соединения напрямую — он вызывает
# методы одного объекта.
#
# Кэш жанров и диапазона годов хранится в атрибутах self
# (self._genres_cache / self._year_range_cache) — считается один раз
# за время жизни объекта, а не при каждом запросе к БД.
# ─────────────────────────────────────────────

import sys
import os
from contextlib import contextmanager

# Добавляем корень проекта в sys.path — нужно, чтобы найти
# local_settings.py, даже если файл запущен напрямую:
#   python app/repositories/film_repository.py
# __file__ = .../itch_films_OOP/app/repositories/film_repository.py
# dirname × 3 → .../itch_films_OOP/
project_root: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)

import mysql.connector
import local_settings


class FilmRepository:
    """
    Repository для чтения данных о фильмах из Sakila (MySQL, только чтение).

    Одна инстанция создаётся один раз при старте приложения (см.
    routes.py: `film_repository = FilmRepository()`) и переиспользуется
    для всех запросов — благодаря этому кэш жанров/годов реально работает
    (иначе он бы создавался заново на каждый HTTP-запрос).
    """

    def __init__(self, dbconfig: dict | None = None,
                 pool_name: str = "itch_films_read", pool_size: int = 5):
        """
        dbconfig задаётся параметром (а не жёстко local_settings.dbconfig
        внутри метода), чтобы объект можно было создать с другими
        настройками в тестах — не трогая реальную БД.
        """
        self._dbconfig  = local_settings.dbconfig if dbconfig is None else dbconfig
        self._pool_name = pool_name
        self._pool_size = pool_size

        # Кэш на уровне экземпляра — заполняется при первом обращении.
        # None означает "ещё не запрашивали".
        self._genres_cache: list[dict] | None = None
        self._year_range_cache: dict | None = None

    # ── Подключение ──────────────────────────────────────────────

    def _get_connection(self):
        """
        Возвращает подключение к Sakila — из пула соединений.

        pool_name/pool_size: mysql-connector-python сам держит пул уже
        открытых TCP-соединений к удалённому серверу
        ich-db.edu.itcareerhub.de. connection.close() ниже по коду не
        закрывает сокет, а возвращает соединение в пул для следующего
        запроса — без этого каждый вызов делал бы полный TCP+auth
        handshake заново.
        """
        return mysql.connector.connect(
            pool_name=self._pool_name,
            pool_size=self._pool_size,
            **self._dbconfig,
        )

    def _fetch_all(self, query: str, params=()) -> list[tuple]:
        """
        Выполняет SELECT и возвращает ВСЕ строки, сама открывая и
        закрывая соединение.

        conn/cursor закрываются в finally (внутри _cursor() ниже) — если
        execute()/fetchall() упадёт (например, БД временно недоступна),
        соединение всё равно вернётся в пул, а не "зависнет" занятым
        навсегда. Без finally 5 подряд неудачных запросов исчерпали бы
        весь пул (pool_size=5), и сайт перестал бы отвечать даже после
        восстановления MySQL.
        """
        with self._cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def _fetch_one(self, query: str, params=()) -> tuple | None:
        """То же самое, что _fetch_all(), но для запросов с одной строкой результата."""
        with self._cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    @contextmanager
    def _cursor(self):
        """
        Общая часть _fetch_all()/_fetch_one(): открывает соединение и
        курсор, отдаёт курсор вызывающему коду через `with`, и
        гарантированно закрывает и курсор, и соединение — даже если
        внутри блока `with` вылетело исключение.
        """
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            yield cursor
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.close()

    def test_connection(self) -> None:
        """Диагностика: печатает первые 5 фильмов или сообщение об ошибке."""
        try:
            films = self._fetch_all("SELECT film_id, title, release_year FROM film LIMIT 5")

            print("=" * 45)
            print("  Подключение к Sakila: УСПЕХ")
            print("=" * 45)
            print("  Первые 5 фильмов из базы:")
            print("-" * 45)
            for film_id, title, year in films:
                print(f"  [{film_id}] {title} ({year})")
            print("=" * 45)
        except mysql.connector.Error as error:
            print("=" * 45)
            print("  Ошибка подключения к MySQL:")
            print(f"  {error}")
            print("  Проверь local_settings.py")
            print("=" * 45)

    # ── Вспомогательное: превращаем строку результата в словарь ─────
    # Все 4 SELECT-запроса ниже (search_by_title, search_by_genre,
    # get_film_by_id, get_all_films) возвращают одинаковый набор
    # колонок в одинаковом порядке — вынесли маппинг в один метод
    # вместо того, чтобы повторять один и тот же словарь 4 раза.

    @staticmethod
    def _row_to_movie(row) -> dict:
        film_id, title, year, rating, length, genre, description = row
        return {
            "film_id":     film_id,
            "title":       title,
            "year":        int(year) if year else None,
            "rating":      rating,
            "length":      length,
            "genre":       genre,
            "description": description,
        }

    # ── Справочники (кэшируются на всё время жизни объекта) ─────────

    def get_all_genres(self) -> list[dict]:
        """
        Возвращает список всех жанров: [{"id": 1, "name": "Action"}, ...].

        Sakila подключена в режиме "только чтение", список жанров
        практически никогда не меняется — кэшируем в self._genres_cache,
        чтобы не ходить в MySQL на каждой загрузке страницы поиска.

        Возвращает КОПИЮ списка, а не сам закэшированный объект — если
        вызывающий код случайно замутирует результат (например,
        genres.append(...)), это не испортит кэш для всех последующих
        запросов (объект общий на все потоки Flask, см. routes.py).
        """
        if self._genres_cache is None:
            rows = self._fetch_all("SELECT category_id, name FROM category ORDER BY name")
            self._genres_cache = [{"id": row[0], "name": row[1]} for row in rows]
        return list(self._genres_cache)

    def get_year_range(self) -> dict:
        """
        Возвращает {"min_year": ..., "max_year": ...} — границы для
        слайдера лет на странице поиска. Кэшируется по той же причине,
        что и get_all_genres(); тоже возвращает копию, не сам кэш.
        """
        if self._year_range_cache is None:
            row = self._fetch_one("SELECT MIN(release_year), MAX(release_year) FROM film")
            # MIN()/MAX() — агрегатные функции, они ВСЕГДА возвращают ровно
            # одну строку (даже для пустой таблицы — тогда просто с NULL),
            # поэтому row не может быть None. Assert проговаривает это явно
            # и для человека, и для статического анализатора типов.
            assert row is not None
            self._year_range_cache = {
                "min_year": int(row[0]),
                "max_year": int(row[1]),
            }
        return dict(self._year_range_cache)

    # ── Поиск и выборки ──────────────────────────────────────────

    def search_by_title(self, keyword: str, limit: int = 10, offset: int = 0) -> list[dict]:
        """
        Ищет фильмы по части названия (регистр не важен).

        ВАЖНО: используем %s (параметризованный запрос), а не f-строки —
        f-строка внутри SQL была бы SQL-инъекцией, MySQL сам экранирует
        значения, переданные через %s.
        """
        search_pattern = f"%{keyword}%"
        # LEFT JOIN + GROUP BY: у фильма может быть несколько жанров в
        # film_category, без GROUP BY один фильм дал бы несколько строк.
        # MIN(c.name) берёт один (алфавитно первый) жанр из всех.
        query = """
            SELECT f.film_id, f.title, f.release_year, f.rating, f.length,
                   MIN(c.name) AS genre, f.description
            FROM   film f
            LEFT JOIN film_category fc ON f.film_id      = fc.film_id
            LEFT JOIN category      c  ON fc.category_id = c.category_id
            WHERE  f.title LIKE %s
            GROUP BY f.film_id, f.title, f.release_year, f.rating, f.length, f.description
            ORDER  BY f.title
            LIMIT  %s OFFSET %s
        """
        rows = self._fetch_all(query, (search_pattern, limit, offset))
        return [self._row_to_movie(row) for row in rows]

    def search_by_genre(self, genre_name: str, year_from: int | None = None,
                         year_to: int | None = None, limit: int = 10, offset: int = 0) -> list[dict]:
        """
        Ищет фильмы по точному названию жанра, опционально фильтрует
        по диапазону годов выпуска (year_from/year_to = None → без ограничения).
        """
        # Базовое условие — всегда по жанру; год добавляем только если
        # передан. conditions содержит только хардкодные фрагменты SQL,
        # пользовательские значения идут через params (защита от инъекций).
        conditions = ["c.name = %s"]
        params     = [genre_name]

        if year_from is not None:
            conditions.append("f.release_year >= %s")
            params.append(year_from)
        if year_to is not None:
            conditions.append("f.release_year <= %s")
            params.append(year_to)

        params.extend([limit, offset])
        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT f.film_id, f.title, f.release_year, f.rating, f.length,
                   c.name AS genre, f.description
            FROM   film f
            JOIN   film_category fc ON f.film_id      = fc.film_id
            JOIN   category      c  ON fc.category_id = c.category_id
            WHERE  {where_clause}
            ORDER  BY f.title
            LIMIT  %s OFFSET %s
        """
        rows = self._fetch_all(query, params)
        return [self._row_to_movie(row) for row in rows]

    def get_film_by_id(self, film_id: int) -> dict | None:
        """Возвращает один фильм по film_id (используется, например, при регенерации постера)."""
        row = self._fetch_one("""
            SELECT f.film_id, f.title, f.release_year, f.rating, f.length,
                   MIN(c.name) AS genre, f.description
            FROM   film f
            LEFT JOIN film_category fc ON f.film_id      = fc.film_id
            LEFT JOIN category      c  ON fc.category_id = c.category_id
            WHERE  f.film_id = %s
            GROUP BY f.film_id, f.title, f.release_year, f.rating, f.length, f.description
        """, (film_id,))
        return self._row_to_movie(row) if row else None

    def get_all_films(self, limit: int = 24, offset: int = 0) -> list[dict]:
        """Возвращает все фильмы Sakila с пагинацией — используется галереей постеров."""
        query = """
            SELECT f.film_id, f.title, f.release_year, f.rating, f.length,
                   MIN(c.name) AS genre, f.description
            FROM   film f
            LEFT JOIN film_category fc ON f.film_id      = fc.film_id
            LEFT JOIN category      c  ON fc.category_id = c.category_id
            GROUP BY f.film_id, f.title, f.release_year, f.rating, f.length, f.description
            ORDER BY f.film_id
            LIMIT  %s OFFSET %s
        """
        rows = self._fetch_all(query, (limit, offset))
        return [self._row_to_movie(row) for row in rows]

    def get_total_films(self) -> int:
        """Общее количество фильмов в Sakila — нужно для пагинации галереи."""
        row = self._fetch_one("SELECT COUNT(*) FROM film")
        assert row is not None  # COUNT(*) всегда возвращает одну строку
        return row[0]


# Ручной прогон диагностики: python app/repositories/film_repository.py
# При импорте модуля (from app.repositories import FilmRepository)
# этот блок не выполняется.
if __name__ == "__main__":
    repo = FilmRepository()

    repo.test_connection()

    print("\n  Жанры из Sakila:")
    print("-" * 45)
    for genre in repo.get_all_genres():
        print(f"  [{genre['id']}] {genre['name']}")

    years = repo.get_year_range()
    print(f"\n  Годы выпуска: {years['min_year']} – {years['max_year']}")

    print("\n  Поиск фильмов по слову 'love':")
    print("-" * 45)
    for movie in repo.search_by_title("love"):
        print(f"  {movie['title']} ({movie['year']}) | {movie['rating']} | {movie['length']} мин")
