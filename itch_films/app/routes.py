# ─────────────────────────────────────────────
# app/routes.py
# Все маршруты (URL-адреса) приложения.
# ─────────────────────────────────────────────

import os

from flask import render_template, request, jsonify, send_from_directory
from app import app
from app.mysql_connector import (
    search_movies_by_title,
    search_movies_by_genre,
    get_all_genres,
    get_year_range,
    get_all_films,
    get_total_films,
    get_film_by_id,
)
from app.mongo_logger import log_search
from app.log_stats import (
    get_popular_searches, get_recent_searches,
    get_total_searches, get_unique_queries,
    get_all_searches, get_unique_searches,
)

# Пути относительно этого файла (itch_films/app/routes.py)
# dirname x1 → itch_films/app/
# dirname x2 → itch_films/
# dirname x3 → Project_IT_Career_Hub_2/  (корень проекта)
_this_dir    = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.normpath(os.path.join(_this_dir, '..', '..'))
POSTERS_DIR  = os.path.join(_project_root, 'storage', 'posters')

# sys.path на корень проекта настраивается один раз в app/__init__.py
# (там же, где подключается Firecrawl-blueprint) — до импорта этого файла.

# Запасное изображение, если постер не найден в таблице movie_posters.
DEFAULT_POSTER = '/static/images/placeholder_movie.png'

# Допустимый диапазон годов для формы поиска "жанр + годы".
YEAR_MIN = 1990
YEAR_MAX = 2026


def _parse_year(value: str):
    """
    Проверяет строку года из формы поиска.

    Пустая строка — год не указан, фильтр по нему не применяется (это не ошибка).
    Иначе строка должна быть целым числом в диапазоне [YEAR_MIN, YEAR_MAX].

    Возвращает (год: int | None, текст_ошибки: str | None).
    """
    if not value:
        return None, None
    try:
        year = int(value)
    except ValueError:
        return None, f"Год должен быть числом от {YEAR_MIN} до {YEAR_MAX}."
    if year < YEAR_MIN or year > YEAR_MAX:
        return None, f"Год должен быть в диапазоне от {YEAR_MIN} до {YEAR_MAX}."
    return year, None


def _enrich_with_posters(movies: list) -> None:
    """
    Добавляет image_url в каждый словарь фильма из write-БД movie_posters.

    Использует PosterRepository.get_latest_by_film_ids() — один запрос к БД
    на всю страницу результатов вместо N отдельных вызовов.
    При недоступности таблицы возвращает DEFAULT_POSTER.
    """
    try:
        from services.ai_posters import PosterRepository
        repo     = PosterRepository()
        film_ids = [m['film_id'] for m in movies]
        posters  = repo.get_latest_by_film_ids(film_ids)
    except Exception:
        posters = {}

    for movie in movies:
        record = posters.get(movie['film_id'])
        movie['image_url'] = record['image_url'] if record else DEFAULT_POSTER


@app.route("/posters/<filename>")
def serve_poster(filename):
    """Отдаёт AI-сгенерированные файлы постеров из storage/posters/."""
    return send_from_directory(POSTERS_DIR, filename)


@app.route("/")
def home():
    try:
        genres = get_all_genres()
    except Exception:
        genres = []

    try:
        year_range = get_year_range()
    except Exception:
        year_range = {"min_year": 2006, "max_year": 2006}

    return render_template("index.html",
                           movies=None, query="", genre="",
                           year_from="", year_to="", offset=0,
                           genres=genres, year_range=year_range,
                           default_image=DEFAULT_POSTER, db_error=None)


@app.route("/search")
def search():
    query     = request.args.get("q",         "").strip()
    genre     = request.args.get("genre",     "").strip()
    year_from = request.args.get("year_from", "").strip()
    year_to   = request.args.get("year_to",   "").strip()

    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0

    movies   = None
    db_error = None

    # ── Проверяем годы ДО похода в базу: "от" и "до" должны быть числами
    # в диапазоне YEAR_MIN..YEAR_MAX, иначе поиск не выполняется вообще.
    yf, year_error = _parse_year(year_from)
    if not year_error:
        yt, year_error = _parse_year(year_to)
    else:
        yt = None
    if not year_error and yf is not None and yt is not None and yf > yt:
        year_error = '«Год от» не может быть больше «Год до».'

    if year_error:
        movies = []
    else:
        try:
            if query:
                movies = search_movies_by_title(query, offset=offset)

            if not movies and genre:
                movies = search_movies_by_genre(genre,
                                                year_from=yf, year_to=yt,
                                                offset=offset)
        except Exception:
            db_error = ("База данных временно недоступна. "
                        "Попробуйте позже.")
            movies = []

    # ── Логируем поиск в MongoDB (некорректные годы не логируем) ──
    results_count = len(movies) if movies else 0
    if year_error:
        pass
    elif query:
        log_search(search_type="title", search_value=query,
                   results_count=results_count)
    elif genre:
        log_search(search_type="genre", search_value=genre,
                   genre=genre, year_from=year_from, year_to=year_to,
                   results_count=results_count)

    # ── Добавляем постеры из movie_posters (write DB) ─────────────
    if movies:
        _enrich_with_posters(movies)

    try:
        genres = get_all_genres()
    except Exception:
        genres = []

    try:
        year_range = get_year_range()
    except Exception:
        year_range = {"min_year": 2006, "max_year": 2006}

    return render_template("index.html",
                           movies=movies, query=query, genre=genre,
                           year_from=year_from, year_to=year_to,
                           offset=offset, genres=genres,
                           year_range=year_range,
                           default_image=DEFAULT_POSTER,
                           db_error=db_error, year_error=year_error)


@app.route("/api/suggest")
def suggest():
    """Autocomplete: возвращает до 5 фильмов по части названия (JSON)."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    try:
        films = search_movies_by_title(q, limit=5) or []
    except Exception:
        return jsonify([])
    return jsonify([
        {"title": f["title"],
         "genre": f.get("genre") or "",
         "year":  f.get("year")  or ""}
        for f in films
    ])


@app.route("/api/film/news")
def film_news():
    """GET /api/film/news?title=<название> — информация о фильме через Firecrawl."""
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({"error": "Не указано название фильма"}), 400

    from app.film_news import get_film_news
    results = get_film_news(title)
    return jsonify({"title": title, "results": results})


@app.route("/gallery")
def gallery():
    """Галерея всех AI-постеров. 24 фильма на страницу."""
    PAGE_SIZE = 24

    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0

    try:
        films = get_all_films(limit=PAGE_SIZE, offset=offset)
        total = get_total_films()
    except Exception:
        films = []
        total = 0

    if films:
        _enrich_with_posters(films)

    return render_template(
        "gallery.html",
        films=films,
        total=total,
        offset=offset,
        page_size=PAGE_SIZE,
        default_image=DEFAULT_POSTER,
    )


@app.route("/api/poster/regenerate", methods=["POST"])
def api_poster_regenerate():
    """
    POST /api/poster/regenerate
    Тело запроса: {"film_id": 42}
    Ответ: {"image_url": "/posters/001102.webp"}
           или {"error": "..."}

    Генерирует новый постер для одного фильма вне очереди.
    Всегда создаёт новую запись в movie_posters (намеренная регенерация).
    """
    data    = request.get_json(silent=True) or {}
    film_id = data.get("film_id")

    if not film_id:
        return jsonify({"error": "film_id required"}), 400

    try:
        film_id = int(film_id)
    except (ValueError, TypeError):
        return jsonify({"error": "film_id must be an integer"}), 400

    film = get_film_by_id(film_id)
    if not film:
        return jsonify({"error": f"Film {film_id} not found in Sakila"}), 404

    try:
        from services.ai_posters import (
            MockProvider, PosterStorage, PosterRepository, PosterService,
        )
        service = PosterService(
            provider=MockProvider(),
            storage=PosterStorage(POSTERS_DIR),
            repository=PosterRepository(),
        )
        service.generate(
            film_id=film["film_id"],
            title=film["title"],
            genre=film["genre"] or "",
            description=film["description"] or "",
        )
        url = service.get_poster_url(film["film_id"])
        return jsonify({"image_url": url})

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/stats/searches")
def stats_searches():
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0
    items = get_all_searches(limit=10, offset=offset)
    total = get_total_searches()
    return render_template("stats_list.html",
                           items=items, total=total, offset=offset,
                           list_type="searches",
                           title="Все поиски")


@app.route("/stats/unique")
def stats_unique():
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0
    items = get_unique_searches(limit=10, offset=offset)
    total = get_unique_queries()
    return render_template("stats_list.html",
                           items=items, total=total, offset=offset,
                           list_type="unique",
                           title="Уникальные запросы")


@app.route("/stats")
def stats():
    popular = get_popular_searches(5)
    recent  = get_recent_searches(5)
    total   = get_total_searches()
    unique  = get_unique_queries()

    return render_template("stats.html",
                           popular=popular, recent=recent,
                           total=total, unique=unique)