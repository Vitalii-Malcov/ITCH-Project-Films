"""
Тесты для create_app() (app/__init__.py) и рендеринга маршрутов через Blueprint.

Зачем этот файл: после перехода routes.py на Blueprint регистрация роутов
проверяется одним smoke-тестом (test_create_app_registers_all_routes), но
это не гарантирует, что render_template() внутри view-функций реально
находит шаблоны — Blueprint без явного template_folder ищет шаблоны в
app.template_folder, и это стоит проверить кодом, а не только глазами.

Правила:
    - film_repository/poster_enricher/search_logger — реальные объекты,
      созданные один раз при первом импорте app.routes (см. сам файл).
      MySQL/MongoDB в тестовом окружении недоступны, поэтому подменяем
      МЕТОДЫ уже созданных объектов через monkeypatch, а не патчим классы
      до импорта — патч класса сработал бы только при самом первом
      импорте модуля за весь pytest-процесс и был бы хрупким к порядку
      запуска тестов.
    - Blueprint можно регистрировать в несколько Flask-приложений — каждый
      тест получает свой app = create_app() и свой test_client().
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
def mock_repository(monkeypatch):
    monkeypatch.setattr(routes_module.film_repository, "get_all_genres",
                         lambda: ["Action", "Comedy"])
    monkeypatch.setattr(routes_module.film_repository, "get_year_range",
                         lambda: {"min_year": 2000, "max_year": 2020})
    monkeypatch.setattr(routes_module.film_repository, "search_by_title",
                         lambda *a, **kw: [
                             {"title": "Test Film", "genre": "Action",
                              "year": 2010, "film_id": 1}
                         ])
    monkeypatch.setattr(routes_module.film_repository, "count_by_title",
                         lambda *a, **kw: 1)
    monkeypatch.setattr(routes_module.film_repository, "search_by_genre",
                         lambda *a, **kw: [])
    monkeypatch.setattr(routes_module.film_repository, "count_by_genre",
                         lambda *a, **kw: 0)
    monkeypatch.setattr(routes_module.film_repository, "search_by_year_range",
                         lambda *a, **kw: [])
    monkeypatch.setattr(routes_module.film_repository, "count_by_year_range",
                         lambda *a, **kw: 0)
    monkeypatch.setattr(routes_module.film_repository, "get_all_films",
                         lambda *a, **kw: [])
    monkeypatch.setattr(routes_module.film_repository, "get_total_films",
                         lambda: 0)
    monkeypatch.setattr(routes_module.poster_enricher, "enrich",
                         lambda movies: None)
    monkeypatch.setattr(routes_module.search_logger, "log_search",
                         lambda **kw: None)


def test_create_app_registers_all_routes(app):
    """Blueprint зарегистрирован и все 9 маршрутов на месте."""
    rules = {r.rule for r in app.url_map.iter_rules()}
    expected = {
        "/", "/search", "/gallery", "/stats", "/stats/searches", "/stats/unique",
        "/api/suggest", "/api/film/news", "/posters/<filename>",
    }
    assert expected.issubset(rules)


def test_home_renders_search_form(client):
    r = client.get("/")
    assert r.status_code == 200


def test_search_renders_results_from_repository(client):
    r = client.get("/search?q=Test")
    assert r.status_code == 200
    assert b"Test Film" in r.data


def test_gallery_renders(client):
    r = client.get("/gallery")
    assert r.status_code == 200


def test_api_suggest_returns_json(client):
    r = client.get("/api/suggest?q=te")
    assert r.status_code == 200
    assert r.get_json() == [{"title": "Test Film", "genre": "Action", "year": 2010}]