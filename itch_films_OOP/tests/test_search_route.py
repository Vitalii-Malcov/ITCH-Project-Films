"""
tests/test_search_route.py
Route-тесты для последних изменений в /search (app/routes.py):
    - мультижанр: объединение (не пересечение) + реальный total_count
      вместо размера страницы
    - регистронезависимая статистика: search_value уходит в MongoDB
      в нижнем регистре, но строка результатов показывает то, что
      реально набрал пользователь
    - пагинация ("Следующие 10") не создаёт повторных записей в
      статистике — логируется только offset == 0
    - "Год от" > "Год до" — автоматическая перестановка вместо ошибки
    - поиск только по диапазону годов, без жанра и названия
    - пустой/пробельный запрос — понятное сообщение, не в статистику
    - веб-роут сброса статистики (/stats/reset, /stats/admin) удалён —
      сброс теперь только консольным scripts/reset_stats.py

MySQL/MongoDB в тестовом окружении недоступны (см. docstring
test_create_app.py) — film_repository и search_logger подменяются через
monkeypatch на уже созданных объектах-синглтонах из app.routes, а не
патчатся на уровне класса.
"""

import pytest

from app import create_app
from app import routes as routes_module


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_search_form_context(monkeypatch):
    """
    Общие моки, нужные ЛЮБОМУ запросу к /search: _get_search_form_context()
    вызывается в конце search() всегда, независимо от того, что искали, и
    poster_enricher.enrich() трогает write-БД, которой в тестах тоже нет.
    """
    monkeypatch.setattr(routes_module.film_repository, "get_all_genres",
                         lambda: [{"id": 1, "name": "Action"}, {"id": 2, "name": "Comedy"}])
    monkeypatch.setattr(routes_module.film_repository, "get_year_range",
                         lambda: {"min_year": 1990, "max_year": 2026})
    monkeypatch.setattr(routes_module.poster_enricher, "enrich", lambda movies: None)


def _dummy_movie(film_id=1, title="Dummy Film"):
    return {"film_id": film_id, "title": title, "year": 2010,
            "rating": "PG", "length": 90, "genre": "Action", "description": "desc"}


def _silence_logger(monkeypatch):
    """Когда тест не проверяет сам факт логирования — просто гасим запись."""
    monkeypatch.setattr(routes_module.search_logger, "log_search", lambda **kw: None)


# ── Мультижанр: объединение + реальный total_count ─────────────────────

class TestMultiGenreSearch:
    def test_multiple_genre_params_read_as_list(self, client, monkeypatch):
        captured = {}

        def fake_search_by_genre(genre_names, **kw):
            captured["genre_names"] = genre_names
            return [_dummy_movie()]

        monkeypatch.setattr(routes_module.film_repository, "search_by_genre", fake_search_by_genre)
        monkeypatch.setattr(routes_module.film_repository, "count_by_genre", lambda genre_names, **kw: 123)
        _silence_logger(monkeypatch)

        r = client.get("/search?genre=Action&genre=Comedy")

        assert r.status_code == 200
        assert captured["genre_names"] == ["Action", "Comedy"]

    def test_shows_real_total_not_page_size(self, client, monkeypatch):
        # search_by_genre "возвращает" всего 1 фильм (одну страницу), но
        # count_by_genre говорит, что их реально 123 — на странице должно
        # быть видно 123, а не 1 (размер того, что вернул search_by_genre).
        monkeypatch.setattr(routes_module.film_repository, "search_by_genre",
                             lambda genre_names, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_genre",
                             lambda genre_names, **kw: 123)
        _silence_logger(monkeypatch)

        r = client.get("/search?genre=Action")

        assert b"123" in r.data

    def test_results_header_lists_all_selected_genres(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_genre",
                             lambda genre_names, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_genre",
                             lambda genre_names, **kw: 2)
        _silence_logger(monkeypatch)

        r = client.get("/search?genre=Action&genre=Comedy")

        assert "Action, Comedy".encode() in r.data


# ── Регистронезависимая статистика ──────────────────────────────────────

class TestCaseInsensitiveStats:
    def test_search_value_logged_lowercase(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                             lambda q, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_title", lambda q: 1)

        logged = {}
        monkeypatch.setattr(routes_module.search_logger, "log_search",
                             lambda **kw: logged.update(kw))

        client.get("/search?q=LOVE")

        assert logged["search_value"] == "love"

    def test_different_case_same_query_logs_same_value(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                             lambda q, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_title", lambda q: 1)

        logged_values = []
        monkeypatch.setattr(routes_module.search_logger, "log_search",
                             lambda **kw: logged_values.append(kw["search_value"]))

        client.get("/search?q=LOVE")
        client.get("/search?q=love")
        client.get("/search?q=LoVe")

        assert logged_values == ["love", "love", "love"]

    def test_displayed_query_keeps_original_case(self, client, monkeypatch):
        # Нормализация — только для MongoDB. Пользователь должен видеть
        # в строке результатов ровно то, что сам набрал.
        monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                             lambda q, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_title", lambda q: 1)
        _silence_logger(monkeypatch)

        r = client.get("/search?q=LOVE")

        assert b"LOVE" in r.data


# ── Пагинация не создаёт повторных записей в статистике ─────────────────

class TestPaginationDoesNotReLog:
    def test_first_page_logs_exactly_once(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                             lambda q, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_title", lambda q: 100)
        calls = []
        monkeypatch.setattr(routes_module.search_logger, "log_search",
                             lambda **kw: calls.append(kw))

        client.get("/search?q=r&offset=0")

        assert len(calls) == 1

    def test_subsequent_pages_do_not_log(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                             lambda q, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_title", lambda q: 100)
        calls = []
        monkeypatch.setattr(routes_module.search_logger, "log_search",
                             lambda **kw: calls.append(kw))

        client.get("/search?q=r&offset=0")
        client.get("/search?q=r&offset=10")
        client.get("/search?q=r&offset=20")

        assert len(calls) == 1, f"Ожидалась 1 запись в лог за 3 запроса, получили {len(calls)}"

    def test_total_count_stays_consistent_across_pages(self, client, monkeypatch):
        # Пагинация не должна пересчитывать total_count заново с других
        # предпосылок — на каждой странице должно быть одно и то же число.
        monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                             lambda q, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_title", lambda q: 701)
        _silence_logger(monkeypatch)

        r1 = client.get("/search?q=r&offset=0")
        r2 = client.get("/search?q=r&offset=10")

        assert b"701" in r1.data
        assert b"701" in r2.data


# ── "Год от" > "Год до" — перестановка вместо ошибки ─────────────────────

class TestYearSwap:
    def test_reversed_years_show_no_error(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_genre",
                             lambda genre_names, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_genre",
                             lambda genre_names, **kw: 1)
        _silence_logger(monkeypatch)

        r = client.get("/search?genre=Action&year_from=2026&year_to=2020")

        assert r.status_code == 200
        assert b"alert-db-error" not in r.data

    def test_reversed_years_swapped_before_hitting_repository(self, client, monkeypatch):
        captured = {}

        def fake_search_by_genre(genre_names, year_from=None, year_to=None, **kw):
            captured["year_from"] = year_from
            captured["year_to"] = year_to
            return [_dummy_movie()]

        monkeypatch.setattr(routes_module.film_repository, "search_by_genre", fake_search_by_genre)
        monkeypatch.setattr(routes_module.film_repository, "count_by_genre",
                             lambda genre_names, **kw: 1)
        _silence_logger(monkeypatch)

        client.get("/search?genre=Action&year_from=2026&year_to=2020")

        assert captured["year_from"] == 2020
        assert captured["year_to"] == 2026

    def test_form_fields_display_swapped_values(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_genre",
                             lambda genre_names, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_genre",
                             lambda genre_names, **kw: 1)
        _silence_logger(monkeypatch)

        r = client.get("/search?genre=Action&year_from=2026&year_to=2020")

        assert b'value="2020"' in r.data
        assert b'value="2026"' in r.data

    def test_equal_years_are_not_touched(self, client, monkeypatch):
        """Год от == Год до — валидный диапазон в одну точку, не "перепутанный"."""
        captured = {}

        def fake_search_by_genre(genre_names, year_from=None, year_to=None, **kw):
            captured["year_from"] = year_from
            captured["year_to"] = year_to
            return [_dummy_movie()]

        monkeypatch.setattr(routes_module.film_repository, "search_by_genre", fake_search_by_genre)
        monkeypatch.setattr(routes_module.film_repository, "count_by_genre",
                             lambda genre_names, **kw: 1)
        _silence_logger(monkeypatch)

        client.get("/search?genre=Action&year_from=2020&year_to=2020")

        assert captured["year_from"] == 2020
        assert captured["year_to"] == 2020


# ── Поиск только по диапазону годов ──────────────────────────────────────

class TestYearOnlySearch:
    def test_year_range_without_genre_or_query_hits_year_repository_method(self, client, monkeypatch):
        captured = {}

        def fake_search_by_year_range(yf, yt, **kw):
            captured["yf"] = yf
            captured["yt"] = yt
            return [_dummy_movie()]

        monkeypatch.setattr(routes_module.film_repository, "search_by_year_range", fake_search_by_year_range)
        monkeypatch.setattr(routes_module.film_repository, "count_by_year_range", lambda yf, yt: 725)
        _silence_logger(monkeypatch)

        r = client.get("/search?year_from=2000&year_to=2026")

        assert captured["yf"] == 2000
        assert captured["yt"] == 2026
        assert b"725" in r.data

    def test_shows_year_label_not_genre_or_query_label(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_year_range",
                             lambda yf, yt, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_year_range", lambda yf, yt: 5)
        _silence_logger(monkeypatch)

        r = client.get("/search?year_from=2000&year_to=2026")

        assert "Годы:".encode() in r.data

    def test_not_treated_as_empty_search(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_year_range",
                             lambda yf, yt, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_year_range", lambda yf, yt: 5)
        _silence_logger(monkeypatch)

        r = client.get("/search?year_from=2000&year_to=2026")

        assert "Пустой запрос".encode() not in r.data

    def test_only_lower_bound_still_searches(self, client, monkeypatch):
        captured = {}

        def fake_search_by_year_range(yf, yt, **kw):
            captured["yf"] = yf
            captured["yt"] = yt
            return [_dummy_movie()]

        monkeypatch.setattr(routes_module.film_repository, "search_by_year_range", fake_search_by_year_range)
        monkeypatch.setattr(routes_module.film_repository, "count_by_year_range", lambda yf, yt: 183)
        _silence_logger(monkeypatch)

        client.get("/search?year_from=2020")

        assert captured["yf"] == 2020
        assert captured["yt"] is None


# ── Кириллица в поиске: честное сообщение вместо "ничего не найдено" ──

class TestCyrillicQuery:
    """
    Sakila целиком на английском — запрос на кириллице ГАРАНТИРОВАННО
    не найдёт ни одного фильма. routes.py даже не должен ходить в MySQL
    за таким запросом (заведомо пустой результат) и не должен писать его
    в MongoDB как обычный неудачный поиск.
    """

    def test_does_not_call_search_by_title(self, client, monkeypatch):
        called = []
        monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                             lambda q, **kw: called.append(q) or [])
        _silence_logger(monkeypatch)

        client.get("/search?q=%D0%BB%D1%8E%D0%B1%D0%BE%D0%B2%D1%8C")  # "любовь"

        assert called == [], "Кириллический запрос не должен доходить до MySQL"

    def test_shows_english_hint_message(self, client, monkeypatch):
        _silence_logger(monkeypatch)

        r = client.get("/search?q=%D0%BB%D1%8E%D0%B1%D0%BE%D0%B2%D1%8C")  # "любовь"

        assert r.status_code == 200
        assert "Введите название на английском".encode() in r.data

    def test_does_not_log_to_stats(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(routes_module.search_logger, "log_search",
                             lambda **kw: calls.append(kw))

        client.get("/search?q=%D0%BB%D1%8E%D0%B1%D0%BE%D0%B2%D1%8C")  # "любовь"

        assert calls == []

    def test_movies_is_not_none_so_message_actually_renders(self, client, monkeypatch):
        # Регрессия: если movies случайно останется None (а не []), секция
        # результатов вообще не отрисуется — сообщение будет ЕСТЬ в шаблоне,
        # но пользователь его не увидит. Проверяем именно то, что рендерится.
        _silence_logger(monkeypatch)

        r = client.get("/search?q=%D0%BB%D1%8E%D0%B1%D0%BE%D0%B2%D1%8C")  # "любовь"

        assert b"results-panel" in r.data

    def test_genre_fallback_still_works_alongside_cyrillic_title(self, client, monkeypatch):
        # Кириллица в поле названия не должна блокировать параллельно
        # выбранный жанр — это независимый, рабочий фильтр.
        captured = {}

        def fake_search_by_genre(genre_names, **kw):
            captured["genre_names"] = genre_names
            return [_dummy_movie()]

        monkeypatch.setattr(routes_module.film_repository, "search_by_genre", fake_search_by_genre)
        monkeypatch.setattr(routes_module.film_repository, "count_by_genre", lambda genre_names, **kw: 65)
        _silence_logger(monkeypatch)

        r = client.get("/search?q=%D0%BB%D1%8E%D0%B1%D0%BE%D0%B2%D1%8C&genre=Action")  # "любовь"

        assert captured["genre_names"] == ["Action"]
        assert b"65" in r.data
        assert "Введите название на английском".encode() not in r.data

    def test_latin_query_is_not_affected(self, client, monkeypatch):
        monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                             lambda q, **kw: [_dummy_movie()])
        monkeypatch.setattr(routes_module.film_repository, "count_by_title", lambda q: 10)
        _silence_logger(monkeypatch)

        r = client.get("/search?q=love")

        assert "Введите название на английском".encode() not in r.data
        assert b"10" in r.data


# ── Пустой / пробельный запрос ────────────────────────────────────────

class TestEmptySearch:
    def test_empty_query_shows_message_and_does_not_log(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(routes_module.search_logger, "log_search",
                             lambda **kw: calls.append(kw))

        r = client.get("/search?q=")

        assert "Пустой запрос".encode() in r.data
        assert calls == []

    def test_whitespace_only_query_shows_message_and_does_not_log(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(routes_module.search_logger, "log_search",
                             lambda **kw: calls.append(kw))

        r = client.get("/search?q=%20%20%20")

        assert "Пустой запрос".encode() in r.data
        assert calls == []

    def test_no_params_at_all_shows_message(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(routes_module.search_logger, "log_search",
                             lambda **kw: calls.append(kw))

        r = client.get("/search")

        assert "Пустой запрос".encode() in r.data
        assert calls == []


# ── Веб-роут сброса статистики удалён ────────────────────────────────

class TestResetStatsRemoved:
    """
    Кнопка сброса статистики была публичной веб-формой без какой-либо
    защиты — убрали её полностью, сброс теперь только через консольный
    scripts/reset_stats.py. Оба маршрута (сам сброс и промежуточный
    вариант с HTTP Basic Auth, который тоже не прижился) должны быть
    полностью не зарегистрированы.
    """

    def test_reset_route_returns_404(self, client):
        r = client.post("/stats/reset")
        assert r.status_code == 404

    def test_admin_route_returns_404(self, client):
        r = client.get("/stats/admin")
        assert r.status_code == 404
