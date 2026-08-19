# ─────────────────────────────────────────────
# app/__init__.py
# Этот файл превращает папку app/ в модуль Python и определяет
# create_app() — фабрику Flask-приложения (factory pattern).
#
# Почему фабрика, а не модульная переменная `app = Flask(...)`:
# создание app откладывается до вызова create_app(), поэтому один и
# тот же код может собрать несколько независимых экземпляров
# приложения (например, отдельный instance для тестов с другим
# config) — вместо одного глобального объекта, который создаётся
# один раз в момент импорта модуля и разделяется всеми.
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
#
# Этот фикс НАРОЧНО остаётся на уровне модуля, а не внутри create_app():
# `import local_settings` ниже тоже выполняется на уровне модуля и
# должен резолвиться ПРАВИЛЬНО уже в момент импорта пакета app — тело
# create_app() выполнится только при явном вызове функции, то есть
# позже, чем строка `import local_settings`. Если бы фикс переехал
# внутрь функции, эта страховка сработала бы слишком поздно.
_project_root: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root in sys.path:
    sys.path.remove(_project_root)
sys.path.insert(0, _project_root)

from flask import Flask   # импортируем класс Flask из библиотеки flask
from dotenv import load_dotenv
import local_settings     # импортируем наши настройки

from app.filters import plural_ru


def create_app(config: dict | None = None) -> Flask:
    """
    Фабрика Flask-приложения.

    config — необязательный словарь для переопределения app.config
    (например, в тестах). Без аргументов создаёт "боевой" instance
    с настройками из local_settings и .env — как раньше вело себя
    модульное `app = Flask(__name__)`.
    """
    # .env из itch_films_OOP/ — там лежат ключи OpenAI и Firecrawl.
    load_dotenv(os.path.join(_project_root, ".env"))

    # Создаём Flask-приложение.
    # __name__ говорит Flask: "ищи шаблоны и статику
    # относительно этого файла".
    app = Flask(__name__)

    # Передаём секретный ключ из local_settings в Flask.
    app.secret_key = local_settings.SECRET_KEY

    if config:
        app.config.update(config)

    # Регистрируем кастомный фильтр для склонения слов по числу в шаблонах
    # (например: {{ n | plural_ru('результат', 'результата', 'результатов') }}).
    app.jinja_env.filters["plural_ru"] = plural_ru

    # Импортируем маршруты ПОСЛЕ создания app и регистрируем Blueprint.
    # Импорт внутри функции (а не на уровне модуля) — иначе получился
    # бы циклический импорт: routes.py импортирует из пакета app
    # (app.repositories, app.services), а пакет app ещё не успел бы
    # доимпортироваться сам себя, если бы routes подключался сверху.
    from app.routes import bp
    app.register_blueprint(bp)

    return app