"""
Общие фикстуры для всех тестов.

Правила:
- Реальный .env не используется — тесты не должны зависеть от настоящих API-ключей или credentials.
- Никаких реальных сетевых вызовов.
- Никаких реальных подключений к базе данных.
"""
import pytest

from app import create_app


@pytest.fixture()
def app():
    """Создаёт тестовое Flask-приложение.

    Реальный .env загружается через create_app() via load_dotenv(), но все
    внешние вызовы сервисов (Firecrawl, MongoDB) замоканы в отдельных тестах
    до выполнения любого запроса, поэтому ключ реально никогда не используется.
    """
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture()
def client(app):
    """Тестовый клиент Flask, созданный из тестового приложения."""
    return app.test_client()
