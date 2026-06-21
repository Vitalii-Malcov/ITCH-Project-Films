# ─────────────────────────────────────────────
# app/routes.py
# Все маршруты (URL-адреса) приложения.
# ─────────────────────────────────────────────

from flask import render_template, request
from app import app
from app.mysql_connector import (
    search_movies_by_title,    # поиск по названию
    search_movies_by_genre,    # поиск по жанру (Этап 4)
    get_all_genres,            # список жанров для фильтра
    # search_movies_by_year,   # Этап 5 — добавим позже
)
from app.movie_images import get_movie_image, DEFAULT_IMAGE, GENRE_IMAGES
from app.mongo_logger import log_search
from app.log_stats import (
    get_popular_searches, get_recent_searches,
    get_total_searches, get_unique_queries,
)


@app.route("/")
def home():
    # Загружаем жанры для отображения кнопок-фильтров на главной странице.
    genres = get_all_genres()
    return render_template("index.html",
                           movies=None,
                           query="",
                           genre="",
                           genres=genres,
                           default_image=DEFAULT_IMAGE)


@app.route("/search")
def search():
    # ── Читаем все параметры поиска ───────────────────────────────
    # Все параметры объявляем здесь заранее.
    # Когда добавим фильтр по годам — просто раскомментируем строки ниже.
    query     = request.args.get("q",     "").strip()
    genre     = request.args.get("genre", "").strip()
    # year_from = request.args.get("year_from", "").strip()  # Этап 5
    # year_to   = request.args.get("year_to",   "").strip()  # Этап 5

    movies = None

    # ── Логика поиска ─────────────────────────────────────────────
    # Используем независимые if-блоки, а не elif-цепочку.
    # Это позволяет добавлять новые фильтры без рефакторинга:
    # каждый блок проверяет "если ещё не нашли — попробуй этот фильтр".

    if query:
        movies = search_movies_by_title(query)

    if not movies and genre:
        movies = search_movies_by_genre(genre)

    # Этап 5 — добавить блок сюда:
    # if not movies and (year_from or year_to):
    #     movies = search_movies_by_year(year_from, year_to)

    # ── Логируем поиск в MongoDB ──────────────────────────────────
    # Определяем тип поиска и записываем лог.
    # Если MongoDB недоступна — log_search() вернёт None без ошибки.
    results_count = len(movies) if movies else 0
    if query:
        log_search(search_type="title", search_value=query,
                   results_count=results_count)
    elif genre:
        log_search(search_type="genre", search_value=genre,
                   genre=genre, results_count=results_count)

    # ── Добавляем постеры с разрешением коллизий ─────────────────
    # get_movie_image() выбирает URL по трёхшаговой логике.
    # Resolver следит за used_images: если URL уже назначен другому
    # фильму в этой выдаче — перебирает соседние слоты жанра.
    if movies:
        used_images = set()
        for movie in movies:
            url = get_movie_image(movie["film_id"], movie.get("genre"))

            if url not in used_images:
                # Коллизии нет — используем как есть
                movie["image_url"] = url
                used_images.add(url)
            else:
                # Коллизия: ищем свободный слот в списке жанра
                genre_list = GENRE_IMAGES.get(movie.get("genre"), [])
                n = len(genre_list)
                base_idx = movie["film_id"] % n if n else 0
                alt_url = url  # fallback если все 20 слотов заняты
                for offset in range(1, n):
                    candidate = genre_list[(base_idx + offset) % n]
                    if candidate not in used_images:
                        alt_url = candidate
                        break
                movie["image_url"] = alt_url
                used_images.add(alt_url)

    # Загружаем жанры для фильтра (нужны на странице результатов тоже)
    genres = get_all_genres()

    return render_template("index.html",
                           movies=movies,
                           query=query,
                           genre=genre,
                           genres=genres,
                           default_image=DEFAULT_IMAGE)


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