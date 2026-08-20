"""
tests/test_film_repository.py
Юнит-тесты для новых/изменённых методов FilmRepository:
    - search_by_genre() / count_by_genre() — теперь принимают СПИСОК
      жанров (c.name IN (...)) вместо одного названия
    - search_by_year_range() / count_by_year_range() — поиск только по
      диапазону годов, без обязательного жанра
    - count_by_title() — реальный COUNT(*) для строки "найдено: N"

MySQL в тестовом окружении недоступен, поэтому здесь не проверяется
"правильный ли SQL возвращает результат" (для этого нужна реальная
Sakila), а проверяется "строит ли метод правильный SQL и параметры" —
_fetch_all()/_fetch_one() подменяются через monkeypatch прямо на
экземпляре репозитория (тот же приём, что и в test_create_app.py для
routes_module.film_repository), так что реальное подключение к БД
вообще не создаётся — FilmRepository(dbconfig={}) ничего не открывает,
пока кто-то явно не вызовет _get_connection().
"""

import pytest

from app.repositories import FilmRepository


@pytest.fixture
def repo():
    return FilmRepository(dbconfig={})


def _capture_fetch_all(monkeypatch, repo):
    """Подменяет repo._fetch_all и возвращает dict, куда попадут query/params."""
    captured = {}

    def fake_fetch_all(query, params=()):
        captured["query"] = query
        captured["params"] = list(params)
        return []

    monkeypatch.setattr(repo, "_fetch_all", fake_fetch_all)
    return captured


def _capture_fetch_one(monkeypatch, repo, return_row=(0,)):
    """Подменяет repo._fetch_one и возвращает dict, куда попадут query/params."""
    captured = {}

    def fake_fetch_one(query, params=()):
        captured["query"] = query
        captured["params"] = list(params)
        return return_row

    monkeypatch.setattr(repo, "_fetch_one", fake_fetch_one)
    return captured


# ── search_by_genre() / count_by_genre(): список вместо одного жанра ──

class TestSearchByGenreMultiple:
    def test_single_genre_builds_one_placeholder(self, repo, monkeypatch):
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_genre(["Action"])
        assert "IN (%s)" in captured["query"]
        assert captured["params"][0] == "Action"

    def test_multiple_genres_build_matching_placeholders(self, repo, monkeypatch):
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_genre(["Action", "Comedy", "Drama"])
        assert "IN (%s, %s, %s)" in captured["query"]
        assert captured["params"][:3] == ["Action", "Comedy", "Drama"]

    def test_uses_group_by_to_avoid_duplicate_rows(self, repo, monkeypatch):
        # Фильм, подходящий сразу под два выбранных жанра, не должен
        # дать две строки в результате JOIN — GROUP BY схлопывает их
        # в одну (та же защита, что и в search_by_title()).
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_genre(["Action", "Comedy"])
        assert "GROUP BY" in captured["query"]

    def test_year_bounds_appended_after_genre_placeholders(self, repo, monkeypatch):
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_genre(["Action", "Comedy"], year_from=2000, year_to=2020)
        assert captured["params"][:2] == ["Action", "Comedy"]
        assert 2000 in captured["params"]
        assert 2020 in captured["params"]
        assert "f.release_year >= %s" in captured["query"]
        assert "f.release_year <= %s" in captured["query"]

    def test_limit_offset_appended_last(self, repo, monkeypatch):
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_genre(["Action"], limit=5, offset=15)
        assert captured["params"][-2:] == [5, 15]


class TestCountByGenreMultiple:
    def test_uses_count_distinct(self, repo, monkeypatch):
        captured = _capture_fetch_one(monkeypatch, repo, return_row=(42,))
        result = repo.count_by_genre(["Action", "Comedy"])
        assert result == 42
        assert "COUNT(DISTINCT f.film_id)" in captured["query"]
        assert "IN (%s, %s)" in captured["query"]

    def test_no_limit_offset_in_count_query(self, repo, monkeypatch):
        # count_by_genre не пагинирует — параметров должно быть ровно
        # столько же, сколько условий WHERE (жанры + опционально годы),
        # без двух лишних (limit, offset) на конце, в отличие от
        # search_by_genre().
        captured = _capture_fetch_one(monkeypatch, repo, return_row=(1,))
        repo.count_by_genre(["Action", "Comedy"])
        assert captured["params"] == ["Action", "Comedy"]


# ── search_by_year_range() / count_by_year_range() ────────────────────

class TestSearchByYearRange:
    def test_both_bounds_present(self, repo, monkeypatch):
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_year_range(2000, 2020)
        assert "release_year >= %s" in captured["query"]
        assert "release_year <= %s" in captured["query"]
        assert captured["params"][0] == 2000
        assert captured["params"][1] == 2020

    def test_only_lower_bound(self, repo, monkeypatch):
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_year_range(year_from=2020, year_to=None)
        assert "release_year >= %s" in captured["query"]
        assert "release_year <= %s" not in captured["query"]

    def test_only_upper_bound(self, repo, monkeypatch):
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_year_range(year_from=None, year_to=2010)
        assert "release_year <= %s" in captured["query"]
        assert "release_year >= %s" not in captured["query"]

    def test_no_genre_join_required(self, repo, monkeypatch):
        # Отличие от search_by_genre(): JOIN на film_category/category —
        # LEFT JOIN (необязательный), а не обязательный JOIN, потому что
        # у этого метода нет фильтра по жанру вообще.
        captured = _capture_fetch_all(monkeypatch, repo)
        repo.search_by_year_range(2000, 2020)
        assert "LEFT JOIN film_category" in captured["query"]


class TestCountByYearRange:
    def test_returns_row_value(self, repo, monkeypatch):
        _capture_fetch_one(monkeypatch, repo, return_row=(725,))
        assert repo.count_by_year_range(2000, 2026) == 725

    def test_no_table_alias_needed(self, repo, monkeypatch):
        # У count_by_year_range нет JOIN, поэтому колонка без префикса
        # "f." (в отличие от search_by_year_range, где алиас f нужен
        # из-за LEFT JOIN).
        captured = _capture_fetch_one(monkeypatch, repo, return_row=(1,))
        repo.count_by_year_range(2000, None)
        assert "WHERE release_year >= %s" in captured["query"]


# ── count_by_title(): реальный итог для "найдено: N" ──────────────────

class TestCountByTitle:
    def test_wraps_keyword_in_wildcards(self, repo, monkeypatch):
        captured = _capture_fetch_one(monkeypatch, repo, return_row=(10,))
        result = repo.count_by_title("love")
        assert result == 10
        assert captured["params"] == ["%love%"]

    def test_no_join_needed(self, repo, monkeypatch):
        # Жанр не участвует в фильтре по названию — JOIN на category
        # был бы лишним запросом ради ничего.
        captured = _capture_fetch_one(monkeypatch, repo, return_row=(1,))
        repo.count_by_title("a")
        assert "JOIN" not in captured["query"]
