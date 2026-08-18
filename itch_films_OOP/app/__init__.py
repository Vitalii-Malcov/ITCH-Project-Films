# ─────────────────────────────────────────────
# app/__init__.py
# Этот файл превращает папку app/ в модуль
# Python и создаёт Flask-приложение.
# Он запускается первым при старте сервера.
#
# Firecrawl-клиент лежит в services/firecrawl/ и используется только
# для блока «Подробнее» через FilmNewsService
# (см. app/services/film_news_service.py).
# ─────────────────────────────────────────────

import os
import sys

# Корень itch_films_OOP/ — на один уровень выше этого файла (app/ → itch_films_OOP/).
# Вставляем его в sys.path[0] ПЕРВЫМ ДЕЛОМ, до любых других импортов —
# если IDE или PYTHONPATH уже добавили в sys.path какой-то другой каталог,
# `import local_settings` ниже мог бы найти чужой файл по тому же имени —
# сначала регистрируем себя в начале пути поиска, чтобы наши модули
# гарантированно резолвились первыми.
_project_root: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root in sys.path:
    sys.path.remove(_project_root)
sys.path.insert(0, _project_root)

from flask import Flask   # импортируем класс Flask из библиотеки flask
from dotenv import load_dotenv
import local_settings     # импортируем наши настройки

# .env из itch_films_OOP/ — там лежат ключи OpenAI и Firecrawl.
load_dotenv(os.path.join(_project_root, ".env"))

# Создаём Flask-приложение.
# __name__ говорит Flask: "ищи шаблоны и статику
# относительно этого файла".
app = Flask(__name__)

# Передаём секретный ключ из local_settings в Flask.
app.secret_key = local_settings.SECRET_KEY

# Импортируем маршруты ITCH Films ПОСЛЕ создания app.
# Порядок важен: routes.py использует переменную app,
# которая должна уже существовать к этому моменту.
from app import routes  # noqa: E402, F401