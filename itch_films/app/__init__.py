# ─────────────────────────────────────────────
# app/__init__.py
# Этот файл превращает папку app/ в модуль
# Python и создаёт Flask-приложение.
# Он запускается первым при старте сервера.
#
# Это единственная точка входа всего проекта:
# здесь же подключается Firecrawl API (services/,
# firecrawl_app/) как blueprint, поэтому один
# процесс Flask обслуживает и каталог фильмов,
# и Firecrawl-эндпоинты.
# ─────────────────────────────────────────────

import os
import sys

from flask import Flask   # импортируем класс Flask из библиотеки flask
from dotenv import load_dotenv
import local_settings     # импортируем наши настройки

# Корень проекта (Project_IT_Career_Hub_2/) — на два уровня выше этого файла
# (app/ → itch_films/ → корень). Добавляем его в sys.path здесь, один раз,
# до импорта любых маршрутов — чтобы отсюда были импортируемы services/
# (ai_posters, mongo, firecrawl) и firecrawl_app/ (Firecrawl API).
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# .env из корня проекта — там лежат ключи Firecrawl (FIRECRAWL_API_KEY и т.д.),
# нужные подключаемому ниже blueprint'у.
load_dotenv()

# Создаём Flask-приложение.
# __name__ говорит Flask: "ищи шаблоны и статику
# относительно этого файла".
app = Flask(__name__)

# Передаём секретный ключ из local_settings в Flask.
app.secret_key = local_settings.SECRET_KEY

# Подключаем Firecrawl API как blueprint (роуты /api/scrape, /api/crawl,
# /api/search, /api/extract, /api/history/<collection>).
from firecrawl_app.routes import firecrawl_bp
app.register_blueprint(firecrawl_bp)

# Импортируем маршруты ITCH Films ПОСЛЕ создания app.
# Порядок важен: routes.py использует переменную app,
# которая должна уже существовать к этому моменту.
from app import routes  # noqa: E402, F401