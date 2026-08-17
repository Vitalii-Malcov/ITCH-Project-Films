"""
Unit-тесты для app/services/rate_limiter.py (RateLimiter).

Правила:
    - Время не ждём по-настоящему — monkeypatch'им time.monotonic,
      чтобы тесты были быстрыми и детерминированными.
    - Тесты независимы.
"""

from unittest.mock import patch

from app.services.rate_limiter import RateLimiter


def test_allows_up_to_max_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("ip1") is True
    assert limiter.allow("ip1") is True
    assert limiter.allow("ip1") is True


def test_blocks_after_max_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        limiter.allow("ip1")
    assert limiter.allow("ip1") is False


def test_keys_are_independent():
    """Лимит для одного ключа не должен влиять на другой (разные IP)."""
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("ip1") is True
    assert limiter.allow("ip2") is True
    assert limiter.allow("ip1") is False
    assert limiter.allow("ip2") is False


def test_old_hits_expire_out_of_window():
    limiter = RateLimiter(max_requests=1, window_seconds=60)

    with patch("app.services.rate_limiter.time.monotonic", return_value=1000.0):
        assert limiter.allow("ip1") is True
        assert limiter.allow("ip1") is False

    # Прошло 61 секунда — окно истекло, лимит должен сброситься
    with patch("app.services.rate_limiter.time.monotonic", return_value=1061.0):
        assert limiter.allow("ip1") is True


def test_blocked_attempt_does_not_consume_slot():
    """Заблокированная попытка не должна регистрироваться как использование слота."""
    limiter = RateLimiter(max_requests=1, window_seconds=60)

    with patch("app.services.rate_limiter.time.monotonic", return_value=1000.0):
        assert limiter.allow("ip1") is True
        assert limiter.allow("ip1") is False
        assert limiter.allow("ip1") is False  # всё ещё False, не "разблокировалось" само

    with patch("app.services.rate_limiter.time.monotonic", return_value=1061.0):
        assert limiter.allow("ip1") is True
