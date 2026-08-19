import os
import sys

from flask import Flask, jsonify
from dotenv import load_dotenv


def create_app():
    # .env лежит в itch_films_2/ рядом с этим пакетом (app/../.env) —
    # путь строим от __file__, а не от текущей рабочей директории, чтобы
    # приложение запускалось одинаково и как `python run.py` изнутри
    # itch_films_2/, и как `python itch_films_2/run.py` из корня.
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Вставляем свой корень в sys.path[0] ДО импорта routes (который тянет
    # bare-name пакет services/) — в репозитории рядом лежат ещё два
    # независимых проекта (itch_films, itch_films_OOP) со своими
    # одноимёнными пакетами services/. Без этой строки при засорённом
    # PYTHONPATH (несколько project root'ов сразу) `from services.firecrawl
    # import ...` ниже мог бы найти чужой пакет services/ вместо своего.
    if _project_root in sys.path:
        sys.path.remove(_project_root)
    sys.path.insert(0, _project_root)

    load_dotenv(os.path.join(_project_root, ".env"))

    app = Flask(__name__)

    # Регистрируем blueprint'ы (импорт внутри функции — избегаем циклических импортов)
    from app.routes import firecrawl_bp
    app.register_blueprint(firecrawl_bp)

    # Заглушка на "/" — это API без главной страницы, но 404 на корне
    # выглядит как будто сервер не запустился. Возвращаем список маршрутов.
    @app.route("/")
    def index():
        return jsonify({
            "service": "Firecrawl API",
            "status": "running",
            "endpoints": [
                "POST /api/scrape",
                "POST /api/crawl",
                "POST /api/search",
                "GET /api/history/<collection>",
            ],
        })

    return app