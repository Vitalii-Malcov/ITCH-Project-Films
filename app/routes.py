# ─────────────────────────────────────────────
# app/routes.py
# Все маршруты (URL-адреса) приложения.
# ─────────────────────────────────────────────

from flask import render_template, request, jsonify
from app import app
from app.mysql_connector import (
    search_movies_by_title,   # поиск по названию
    search_movies_by_genre,   # поиск по жанру + опциональный диапазон годов
    get_all_genres,           # список жанров для фильтра
    get_year_range,           # мин/макс год для подсказки в UI
)
from app.movie_images import get_movie_image, DEFAULT_IMAGE, GENRE_IMAGES
from app.mongo_logger import log_search
from app.log_stats import (
    get_popular_searches, get_recent_searches,
    get_total_searches, get_unique_queries,
)


@app.route("/")
def home():
    # Пробел 4: try/except вокруг MySQL — если база недоступна,
    # страница всё равно откроется, просто без жанров и диапазона лет.
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
                           default_image=DEFAULT_IMAGE, db_error=None)


@app.route("/search")
def search():
    # ── Читаем параметры запроса ──────────────────────────────────
    query     = request.args.get("q",         "").strip()
    genre     = request.args.get("genre",     "").strip()
    year_from = request.args.get("year_from", "").strip()  # Пробел 1
    year_to   = request.args.get("year_to",   "").strip()  # Пробел 1

    # Пробел 2: пагинация — offset указывает, сколько фильмов пропустить.
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0

    movies   = None
    db_error = None

    # ── Пробел 4: try/except вокруг MySQL ────────────────────────
    # Если база недоступна — пользователь видит понятное сообщение,
    # а не трейсбек. Сайт продолжает работать без результатов поиска.
    try:
        if query:
            movies = search_movies_by_title(query, offset=offset)

        if not movies and genre:
            # Пробел 1: передаём year_from/year_to как int или None.
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

    # ── Добавляем постеры с разрешением коллизий ─────────────────
    if movies:
        used_images = set()
        for movie in movies:
            url = get_movie_image(movie["film_id"], movie.get("genre"))

            if url not in used_images:
                movie["image_url"] = url
                used_images.add(url)
            else:
                # Коллизия: ищем свободный слот в списке жанра.
                # Переменная step (не offset) — чтобы не затенять
                # параметр пагинации, объявленный выше.
                genre_list = GENRE_IMAGES.get(movie.get("genre"), [])
                n = len(genre_list)
                base_idx = movie["film_id"] % n if n else 0
                alt_url = url
                for step in range(1, n):
                    candidate = genre_list[(base_idx + step) % n]
                    if candidate not in used_images:
                        alt_url = candidate
                        break
                movie["image_url"] = alt_url
                used_images.add(alt_url)

    # ── Пробел 4: жанры и диапазон лет тоже в try/except ─────────
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
                           default_image=DEFAULT_IMAGE,
                           db_error=db_error)


@app.route("/api/suggest")
def suggest():
    """Autocomplete: возвращает до 5 фильмов по части названия (JSON).
    Используется кастомным dropdown на главной странице."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    # Пробел 4: при сбое MySQL возвращаем пустой список —
    # autocomplete молча отключается, форма продолжает работать.
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


@app.route("/stats")
def stats():
    # Читаем статистику из MongoDB.
    # Если MongoDB недоступна — функции вернут [] или 0,
    # страница отобразится с пустыми данными.
    popular = get_popular_searches(5)
    recent  = get_recent_searches(5)
    total   = get_total_searches()
    unique  = get_unique_queries()

    return render_template("stats.html",
                           popular=popular, recent=recent,
                           total=total, unique=unique)