"""
Shared fixtures for all tests.

Rules:
- No real .env is used — tests must not rely on actual API keys or credentials.
- No real network calls.
- No real database connections.
"""
import pytest

# Module-level import: registers the ROOT 'app' package in sys.modules
# before any test can trigger services.ai_posters.poster_repository, which
# does sys.path.insert(0, itch_films/) and could otherwise cause Python to
# resolve 'app' as itch_films/app/ (a different Flask application).
from app import create_app  # noqa: E402


@pytest.fixture()
def app():
    """Create a Flask test application.

    Real .env is loaded by create_app() via load_dotenv(), but all external
    service calls (Firecrawl, MongoDB) are mocked in individual tests before
    any request is made, so the key is never actually used.
    """
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture()
def client(app):
    """Flask test client derived from the test app."""
    return app.test_client()