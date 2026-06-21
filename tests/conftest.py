# ─────────────────────────────────────────────
# tests/conftest.py
# Настройка Playwright для тестов ITCH Films.
#
# ВАЖНО: перед запуском тестов Flask должен быть
# запущен вручную в отдельном терминале:
#   python run.py
#
# Запуск тестов (в видимом браузере):
#   pytest tests/ --headed --slowmo=600 -v
#
# Запуск в фоне (без браузера):
#   pytest tests/ -v
# ─────────────────────────────────────────────

import pytest


# Базовый URL сайта — Flask по умолчанию на 5000.
BASE_URL = "http://127.0.0.1:5000"


@pytest.fixture(scope="session")
def base_url():
    """Передаётся в каждый тест через параметр page.goto(base_url)."""
    return BASE_URL


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Устанавливаем размер окна браузера как у типичного ноутбука."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
    }
