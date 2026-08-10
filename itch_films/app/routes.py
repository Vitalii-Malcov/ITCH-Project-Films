# ─────────────────────────────────────────────
# app/routes.py
# Все маршруты (URL-адреса) приложения.
# ─────────────────────────────────────────────

import os
import sys

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

# Paths relative to this file (itch_films/app/routes.py)
# dirname x1 → itch_films/app/
# dirname x2 → itch_films/
# dirname x3 → Project_IT_Career_Hub_2/  (project root)
_this_dir    = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.normpath(os.path.join(_this_dir, '..', '..'))
POSTERS_DIR  = os.path.join(_project_root, 'storage', 'posters')

# Make services/ importable (services/ lives in project root, not itch_films/)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
# TODO: sys.path manipulation does not belong in routes.py.
#   Find a single initialisation point (e.g. run.py or app/__init__.py)
#   that sets up the project root on sys.path before any routes are loaded,
#   so routes.py can import services without touching sys.path itself.

# Fallback image shown when no poster is found in movie_posters table.
DEFAULT_POSTER = '/static/images/placeholder_movie.png'


def _enrich_with_posters(movies: list) -> None:
    """
    Add image_url to each movie dict using the movie_posters write DB.

    Uses PosterRepository.get_latest_by_film_ids() — one DB query for the
    entire result page instead of N individual calls.
    Falls back to DEFAULT_POSTER if the table is unreachable.
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
    """Serve AI-generated poster files from storage/posters/."""
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

    try:
        if query:
            movies = search_movies_by_title(query, offset=offset)

        if not movies and genre:
            yf = int(year_from) if year_from else None
            yt = int(year_to)   if year_to   else None
            movies = search_movies_by_genre(genre,
                                            year_from=yf, year_to=yt,
                                            offset=offset)
    except Exception:
        db_error = ("База данных временно недоступна. "
                    "Попробуйте позже.")
        movies = []

    # ── Логируем поиск в MongoDB ──────────────────────────────────
    results_count = len(movies) if movies else 0
    if query:
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
                           db_error=db_error)


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
    Body: {"film_id": 42}
    Response: {"image_url": "/posters/001102.webp"}
              или {"error": "..."}

    Генерирует новый постер для одного фильма вне очереди.
    Всегда создаёт новую запись в movie_posters (intentional re-generation).
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