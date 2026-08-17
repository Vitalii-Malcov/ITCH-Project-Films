# ─────────────────────────────────────────────
# app/repositories/__init__.py
# Пакет с классами доступа к данным (Repository pattern).
# ─────────────────────────────────────────────

from app.repositories.film_repository import FilmRepository

__all__ = ["FilmRepository"]
