"""
Unit-тесты для fencing-token логики в GenerationQueue
(services/ai_posters/queue.py: mark_processing/mark_done/mark_failed).

Правила:
    - Никаких реальных подключений к базе данных — mysql.connector.connect
      полностью замокан.
    - Тесты независимы.
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_queue():
    from services.ai_posters.queue import GenerationQueue
    return GenerationQueue()


def _mock_connect(cursor):
    """Патчит GenerationQueue._connect(), чтобы возвращать mock-соединение
    с уже подготовленным mock-курсором."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return patch.object(
        __import__('services.ai_posters.queue', fromlist=['GenerationQueue']).GenerationQueue,
        '_connect',
        return_value=conn,
    )


class TestMarkProcessingClaimToken:
    def test_successful_claim_returns_token_from_db(self):
        """При успешном захвате (rowcount=1) возвращается claim_token, прочитанный из БД."""
        cursor = MagicMock()
        cursor.rowcount = 1
        cursor.fetchone.return_value = (3,)

        queue = _make_queue()
        with _mock_connect(cursor):
            token = queue.mark_processing(queue_id=42)

        assert token == 3

    def test_lost_race_returns_none(self):
        """Если UPDATE ничего не изменил (rowcount=0) — элемент уже не 'pending', возвращается None."""
        cursor = MagicMock()
        cursor.rowcount = 0

        queue = _make_queue()
        with _mock_connect(cursor):
            token = queue.mark_processing(queue_id=42)

        assert token is None
        # SELECT claim_token не должен вызываться, если UPDATE не затронул строк
        cursor.fetchone.assert_not_called()


class TestMarkDoneFencing:
    def test_matching_token_updates_status(self):
        """mark_done с правильным claim_token обновляет статус (rowcount=1)."""
        cursor = MagicMock()
        cursor.rowcount = 1

        queue = _make_queue()
        with _mock_connect(cursor):
            queue.mark_done(queue_id=42, claim_token=3)

        executed_sql = cursor.execute.call_args[0][0]
        assert "claim_token = %s" in executed_sql
        assert "status = 'processing'" in executed_sql
        assert cursor.execute.call_args[0][1] == ('done', 42, 3)

    def test_stale_token_is_ignored(self):
        """
        Устаревший claim_token (элемент уже перезахвачен заново — rowcount=0)
        не должен поднимать исключение — обновление просто не применяется.
        """
        cursor = MagicMock()
        cursor.rowcount = 0

        queue = _make_queue()
        with _mock_connect(cursor):
            queue.mark_done(queue_id=42, claim_token=1)  # не выбрасывает

    def test_no_token_only_updates_pending_item(self):
        """
        Без claim_token (элемент никогда не проходил через mark_processing,
        например film_id отсутствует в Sakila) — обновление всё равно
        ограничено status='pending', чтобы не перезаписать более свежий
        захват элемента.
        """
        cursor = MagicMock()
        cursor.rowcount = 1

        queue = _make_queue()
        with _mock_connect(cursor):
            queue.mark_done(queue_id=42)

        executed_sql = cursor.execute.call_args[0][0]
        assert "claim_token" not in executed_sql
        assert "status = 'pending'" in executed_sql
        assert cursor.execute.call_args[0][1] == ('done', 42)


class TestMarkFailedFencing:
    def test_matching_token_updates_status_and_increments_tries(self):
        cursor = MagicMock()
        cursor.rowcount = 1

        queue = _make_queue()
        with _mock_connect(cursor):
            queue.mark_failed(queue_id=42, claim_token=3)

        executed_sql = cursor.execute.call_args[0][0]
        assert "tries = tries + 1" in executed_sql
        assert "claim_token = %s" in executed_sql
        assert "status = 'processing'" in executed_sql
        assert cursor.execute.call_args[0][1] == (42, 3)

    def test_stale_token_is_ignored(self):
        cursor = MagicMock()
        cursor.rowcount = 0

        queue = _make_queue()
        with _mock_connect(cursor):
            queue.mark_failed(queue_id=42, claim_token=1)  # не выбрасывает
