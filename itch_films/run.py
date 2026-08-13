# ─────────────────────────────────────────────
# run.py
# Единственная точка входа всего проекта: один
# Flask-процесс обслуживает и каталог фильмов
# ITCH Films, и Firecrawl API (подключён как
# blueprint в app/__init__.py).
# Запускай именно этот файл командой:
#   python itch_films/run.py
# ─────────────────────────────────────────────

import os

from app import app   # импортируем объект app из папки app/

if __name__ == "__main__":
    # debug читается из переменной окружения FLASK_DEBUG.
    # По умолчанию (переменная не задана) — False, безопасно для прод-подобного запуска.
    # Чтобы включить debug-режим разработки: FLASK_DEBUG=true python run.py
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug)
