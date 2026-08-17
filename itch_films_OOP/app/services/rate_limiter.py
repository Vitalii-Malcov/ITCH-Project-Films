# ─────────────────────────────────────────────
# app/services/rate_limiter.py
# Простой rate limiter в памяти процесса — без внешних зависимостей
# (Redis, Flask-Limiter и т.п.), под масштаб курсового проекта.
#
# Ограничение: состояние не шарится между процессами/воркерами. Для
# однопроцессного Flask dev-сервера (архитектура этого проекта) этого
# достаточно; при переходе на несколько воркеров нужен внешний стор.
# ─────────────────────────────────────────────

import threading
import time


class RateLimiter:
    """
    Не более max_requests вызовов на один ключ (обычно IP) за скользящее
    окно window_seconds.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self._max_requests = max_requests
        self._window = window_seconds
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        """
        Возвращает True и регистрирует попытку, если лимит для этого
        ключа ещё не исчерпан за последние window_seconds; иначе False
        (попытка НЕ регистрируется).
        """
        now = time.monotonic()
        with self._lock:
            timestamps = self._hits.setdefault(key, [])
            cutoff = now - self._window
            # Отбрасываем устаревшие метки времени с начала списка —
            # timestamps всегда хранится в порядке добавления (по времени).
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)

            if len(timestamps) >= self._max_requests:
                return False

            timestamps.append(now)
            return True
