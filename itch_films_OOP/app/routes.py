# ─────────────────────────────────────────────
# app/routes.py
# Все маршруты (URL-адреса) приложения.
#
# View-функции Flask остаются функциями (это стандартный способ
# объявлять маршруты в Flask — @app.route декорирует функцию), но
# внутри они не открывают соединения и не пишут SQL сами — они
# вызывают методы уже готовых объектов: film_repository, search_logger,
# search_stats, film_news_service, poster_enricher. Все эти объекты
# создаются один раз ниже (после импортов) и переиспользуются на
# каждый запрос — состояние явно принадлежит объектам.
# ─────────────────────────────────────────────

import logging
import os
import sys

# Этот файл предназначен для импорта через create_app() (app/__init__.py),
# а не для прямого запуска. Но если его всё же запустят напрямую
# (`python app/routes.py`) — Python подставляет папку ЭТОГО файла
# (app/) в начало sys.path, а не корень проекта. Если в PYTHONPATH
# уже был путь к какому-то другому каталогу с одноимённым пакетом
# `app`, Python может по ошибке импортировать его вместо нашего.
# Вставляем свой корень первым — так импорты `app.repositories` и
# `app.services` ниже гарантированно найдут именно itch_films_OOP/app/.
_project_root: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root in sys.path:
    sys.path.remove(_project_root)
sys.path.insert(0, _project_root)

from flask import Blueprint, render_template, request, jsonify, send_from_directory
import local_settings

from app.repositories import FilmRepository
from app.services import (
    MongoConnection,
    SearchLogger,
    SearchStatsRepository,
    FilmNewsService,
    PosterEnricher,
    RateLimiter,
)
from services.ai_posters import PosterRepository

logger = logging.getLogger(__name__)

# Blueprint вместо прямого `@bp.route(...)` на глобальном объекте app —
# так routes.py больше не зависит от того, что app уже создан на уровне
# модуля app/__init__.py. create_app() регистрирует этот Blueprint через
# app.register_blueprint(bp) уже ПОСЛЕ того, как Flask-приложение создано.
bp = Blueprint("main", __name__)

# Пути относительно этого файла (itch_films_OOP/app/routes.py)
# dirname x1 → itch_films_OOP/app/
# dirname x2 → itch_films_OOP/  (корень проекта ITCH Films)
_this_dir: str   = os.path.dirname(os.path.abspath(__file__))
_itch_films: str = os.path.normpath(os.path.join(_this_dir, '..'))
POSTERS_DIR: str = os.path.join(_itch_films, 'storage', 'posters')

# sys.path на корень itch_films_OOP/ уже настроен выше (строки 19-31) и
# ещё раз — в app/__init__.py до импорта этого файла (при обычном запуске
# через run.py оба раза указывают на один и тот же путь, повтор безвреден).

# Запасное изображение, если постер не найден в таблице movie_posters.
DEFAULT_POSTER = '/static/images/placeholder_movie.png'

# Допустимый диапазон годов для формы поиска "жанр + годы".
YEAR_MIN = 1990
YEAR_MAX = 2026

# Максимальная длина названия фильма для /api/film/news — Firecrawl это
# платный внешний API, без ограничения запрос можно было слать сколь
# угодно длинной строкой (лишние расходы, не влияя на качество поиска).
FILM_NEWS_TITLE_MAX_LENGTH = 200

# Rate limit для /api/film/news — платный вызов Firecrawl на каждый запрос,
# без аутентификации. У проекта нет системы логина/пользователей (курсовой
# проект без авторизации) — полноценная auth здесь была бы избыточна. Rate
# limit — минимальная защита от одного клиента, заваливающего эндпоинт
# запросами (случайно или намеренно) и раздувающего расходы.
film_news_limiter = RateLimiter(max_requests=10, window_seconds=60)


# ── Сборка объектов сервисного слоя (композиция) ────────────────────
# Создаются один раз при импорте модуля и переиспользуются как явные
# объекты на каждый запрос.

film_repository = FilmRepository()

# Одна и та же MongoDB-коллекция, но два отдельных подключения — по
# одному для записи логов и для чтения статистики. label разный,
# чтобы в терминале было видно, какое именно подключение недоступно.
_write_connection = MongoConnection(
    local_settings.MONGO_URI, local_settings.MONGO_DATABASE,
    local_settings.MONGO_COLLECTION, label="MongoDB",
)
_read_connection = MongoConnection(
    local_settings.MONGO_URI, local_settings.MONGO_DATABASE,
    local_settings.MONGO_COLLECTION, label="MongoDB Stats",
)

search_logger      = SearchLogger(_write_connection)
search_stats        = SearchStatsRepository(_read_connection)
film_news_service   = FilmNewsService()
# PosterRepository передаётся явно (а не создаётся внутри PosterEnricher) —
# тот же принцип dependency injection, что и у остальных сервисов выше.
poster_enricher     = PosterEnricher(DEFAULT_POSTER, poster_repository=PosterRepository())


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


@bp.route("/posters/<filename>")
def serve_poster(filename):
    """Отдаёт AI-сгенерированные файлы постеров из storage/posters/."""
    return send_from_directory(POSTERS_DIR, filename)


def _get_search_form_context() -> tuple[list[dict], dict]:
    """
    Возвращает (genres, year_range) для формы поиска на index.html.

    Используется и в home(), и в search() — в обоих местах нужны одни
    и те же справочники для отрисовки формы (список жанров, границы
    годов), с одинаковым fallback-поведением при недоступности БД.
    Вынесено в один хелпер вместо копии try/except в каждом маршруте.
    """
    try:
        genres = film_repository.get_all_genres()
    except Exception:
        # Логируем полную причину на сервере: этот except обязан
        # ловить и "MySQL недоступна" (ожидаемо), и настоящий баг в
        # коде (неожиданно) — без логирования второе тихо тонет
        # в первом, и обе ситуации выглядят для пользователя одинаково.
        logger.exception("не удалось получить список жанров")
        genres = []

    try:
        year_range = film_repository.get_year_range()
    except Exception:
        logger.exception("не удалось получить диапазон годов")
        year_range = {"min_year": 2006, "max_year": 2006}

    return genres, year_range


@bp.route("/")
def home():
    genres, year_range = _get_search_form_context()

    return render_template("index.html",
                           movies=None, query="", genre="",
                           year_from="", year_to="", offset=0,
                           genres=genres, year_range=year_range,
                           default_image=DEFAULT_POSTER, db_error=None)


@bp.route("/search")
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
                movies = film_repository.search_by_title(query, offset=offset)

            if not movies and genre:
                movies = film_repository.search_by_genre(genre,
                                                          year_from=yf, year_to=yt,
                                                          offset=offset)
        except Exception:
            logger.exception("search: ошибка при поиске (query=%r, genre=%r)", query, genre)
            db_error = ("База данных временно недоступна. "
                        "Попробуйте позже.")
            movies = []

    # ── Логируем поиск в MongoDB (некорректные годы не логируем) ──
    results_count = len(movies) if movies else 0
    if year_error:
        pass
    elif query:
        search_logger.log_search(search_type="title", search_value=query,
                                 results_count=results_count)
    elif genre:
        search_logger.log_search(search_type="genre", search_value=genre,
                                 genre=genre, year_from=year_from, year_to=year_to,
                                 results_count=results_count)

    # ── Добавляем постеры из movie_posters (write DB) ─────────────
    if movies:
        poster_enricher.enrich(movies)

    genres, year_range = _get_search_form_context()

    return render_template("index.html",
                           movies=movies, query=query, genre=genre,
                           year_from=year_from, year_to=year_to,
                           offset=offset, genres=genres,
                           year_range=year_range,
                           default_image=DEFAULT_POSTER,
                           db_error=db_error, year_error=year_error)


@bp.route("/api/suggest")
def suggest():
    """Autocomplete: возвращает до 5 фильмов по части названия (JSON)."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    try:
        films = film_repository.search_by_title(q, limit=5) or []
    except Exception:
        logger.exception("suggest: не удалось выполнить автокомплит (q=%r)", q)
        return jsonify([])
    return jsonify([
        {"title": f["title"],
         "genre": f.get("genre") or "",
         "year":  f.get("year")  or ""}
        for f in films
    ])


@bp.route("/api/film/news")
def film_news():
    """GET /api/film/news?title=<название> — информация о фильме через Firecrawl."""
    if not film_news_limiter.allow(request.remote_addr or "unknown"):
        return jsonify({"error": "Слишком много запросов, попробуйте позже."}), 429

    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({"error": "Не указано название фильма"}), 400
    if len(title) > FILM_NEWS_TITLE_MAX_LENGTH:
        return jsonify({"error": "Слишком длинное название фильма"}), 400

    results = film_news_service.get_film_news(title)
    return jsonify({"title": title, "results": results})


@bp.route("/gallery")
def gallery():
    """Галерея всех AI-постеров. 24 фильма на страницу."""
    page_size = 24

    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0

    try:
        films = film_repository.get_all_films(limit=page_size, offset=offset)
        total = film_repository.get_total_films()
    except Exception:
        logger.exception("gallery: не удалось получить фильмы (offset=%d)", offset)
        films = []
        total = 0

    if films:
        poster_enricher.enrich(films)

    return render_template(
        "gallery.html",
        films=films,
        total=total,
        offset=offset,
        page_size=page_size,
        default_image=DEFAULT_POSTER,
    )


@bp.route("/stats/searches")
def stats_searches():
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0
    items = search_stats.get_all_searches(limit=10, offset=offset)
    total = search_stats.get_total_searches()
    return render_template("stats_list.html",
                           items=items, total=total, offset=offset,
                           list_type="searches",
                           title="Все поиски")


@bp.route("/stats/unique")
def stats_unique():
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0
    items = search_stats.get_unique_searches(limit=10, offset=offset)
    total = search_stats.get_unique_queries()
    return render_template("stats_list.html",
                           items=items, total=total, offset=offset,
                           list_type="unique",
                           title="Уникальные запросы")


@bp.route("/stats")
def stats():
    popular = search_stats.get_popular_searches(5)
    recent  = search_stats.get_recent_searches(5)
    total   = search_stats.get_total_searches()
    unique  = search_stats.get_unique_queries()

    return render_template("stats.html",
                           popular=popular, recent=recent,
                           total=total, unique=unique)
