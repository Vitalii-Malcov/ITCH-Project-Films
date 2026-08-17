# ─────────────────────────────────────────────
# local_settings.example.py
# Шаблон local_settings.py — скопируй в local_settings.py
# и подставь реальные значения. Сам local_settings.py
# в .gitignore и никогда не должен попадать в Git.
#
# Значения ниже — фейковые плейсхолдеры (используются
# в CI для unit-тестов, которые полностью замокан
# и реально к базам не подключаются).
# ─────────────────────────────────────────────

# ── Flask ──────────────────────────────────────
SECRET_KEY = "dev-secret-key"

# ── MySQL: ЧТЕНИЕ (база Sakila с фильмами) ─────
dbconfig = {
    "host":     "localhost",
    "user":     "example_user",
    "password": "example_password",
    "database": "sakila"
}

# ── MySQL: ЗАПИСЬ (личная база студента) ───────
dbconfig_write = {
    "host":     "localhost",
    "user":     "example_user",
    "password": "example_password",
    "database": "example_db"
}

# ── MongoDB ────────────────────────────────────
MONGO_URI        = "mongodb://localhost:27017/"
MONGO_DATABASE   = "itch_films_logs"
MONGO_COLLECTION = "example_collection"
