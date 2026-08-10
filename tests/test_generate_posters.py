"""
Unit tests for scripts/generate_movie_posters.py and the new
PosterRepository.openai_poster_exists / get_openai_completed_film_ids methods.

Rules:
    - No real database connections.
    - No real OpenAI API calls.
    - No file I/O.
    - Tests are fully independent.
"""

import argparse
import pytest
from unittest.mock import MagicMock, patch


# ── Shared test film factory ───────────────────────────────────────────

def _make_film(
    film_id: int = 1,
    title: str = 'TEST FILM',
    description: str = 'A gripping tale of survival.',
    genre: str = 'Drama',
    release_year: int = 2006,
    rating: str = 'PG',
) -> dict:
    return {
        'film_id': film_id,
        'title': title,
        'description': description,
        'genre': genre,
        'release_year': release_year,
        'rating': rating,
    }


def _make_queue_item(film_id: int, queue_id: int | None = None) -> dict:
    return {'id': queue_id or film_id, 'film_id': film_id}


# ── 1. Argument parsing ───────────────────────────────────────────────

class TestParseArgs:

    def _parse(self, argv: list[str]) -> argparse.Namespace:
        from scripts.generate_movie_posters import parse_args
        with patch('sys.argv', ['script'] + argv):
            return parse_args()

    def test_default_limit_is_5(self):
        assert self._parse([]).limit == 5

    def test_default_film_id_is_none(self):
        assert self._parse([]).film_id is None

    def test_default_dry_run_is_false(self):
        assert self._parse([]).dry_run is False

    def test_limit_overridden(self):
        assert self._parse(['--limit', '20']).limit == 20

    def test_film_id_parsed(self):
        assert self._parse(['--film-id', '42']).film_id == 42

    def test_dry_run_flag(self):
        assert self._parse(['--dry-run']).dry_run is True

    def test_combined_film_id_and_dry_run(self):
        args = self._parse(['--film-id', '7', '--dry-run'])
        assert args.film_id == 7
        assert args.dry_run is True


# ── 2. Description fallback logic ─────────────────────────────────────

class TestBuildDescription:

    def _call(self, film: dict) -> tuple[str, bool]:
        from scripts.generate_movie_posters import _build_description
        return _build_description(film)

    def test_normal_description_returned_unchanged(self):
        film = _make_film(description='A gripping drama about loss.')
        desc, is_fallback = self._call(film)
        assert desc == 'A gripping drama about loss.'
        assert is_fallback is False

    def test_none_description_triggers_fallback(self):
        film = _make_film(description=None)
        desc, is_fallback = self._call(film)
        assert is_fallback is True
        assert 'TEST FILM' in desc

    def test_empty_string_triggers_fallback(self):
        film = _make_film(description='')
        _, is_fallback = self._call(film)
        assert is_fallback is True

    def test_whitespace_only_triggers_fallback(self):
        film = _make_film(description='   ')
        _, is_fallback = self._call(film)
        assert is_fallback is True

    def test_fallback_contains_genre(self):
        film = _make_film(genre='Action', description=None)
        desc, _ = self._call(film)
        assert 'Action' in desc

    def test_fallback_does_not_use_film_id(self):
        """Prompt must never be built from film_id alone."""
        film = _make_film(film_id=999, title='STAR FILM', genre='Sci-Fi', description=None)
        desc, _ = self._call(film)
        assert '999' not in desc
        assert 'STAR FILM' in desc

    def test_missing_genre_defaults_to_drama(self):
        film = _make_film(genre=None, description=None)
        desc, _ = self._call(film)
        assert 'Drama' in desc


# ── 3. PosterRepository.openai_poster_exists ──────────────────────────

class TestOpenaiPosterExists:

    def _call(self, fetchone_return) -> tuple[bool, MagicMock]:
        from services.ai_posters.poster_repository import PosterRepository

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = fetchone_return
        mock_conn   = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        repo = PosterRepository()
        with patch('mysql.connector.connect', return_value=mock_conn):
            result = repo.openai_poster_exists(film_id=1)

        return result, mock_cursor

    def test_returns_true_when_openai_poster_exists(self):
        result, _ = self._call(fetchone_return=(1,))
        assert result is True

    def test_returns_false_when_no_openai_poster(self):
        result, _ = self._call(fetchone_return=None)
        assert result is False

    def test_query_filters_by_provider_openai(self):
        _, cursor = self._call(fetchone_return=None)
        sql = cursor.execute.call_args[0][0].lower()
        assert 'openai' in sql

    def test_query_filters_by_status_completed(self):
        _, cursor = self._call(fetchone_return=None)
        sql = cursor.execute.call_args[0][0].lower()
        assert 'completed' in sql

    def test_query_does_not_match_mock_posters(self):
        """The query must explicitly select provider='openai', not any provider."""
        _, cursor = self._call(fetchone_return=None)
        sql = cursor.execute.call_args[0][0].lower()
        # Must filter on provider — not just status
        assert 'provider' in sql


# ── 4. PosterRepository.get_openai_completed_film_ids ────────────────

class TestGetOpenaiCompletedFilmIds:

    def _make_repo_call(self, fetchall_return: list) -> tuple[set, MagicMock]:
        from services.ai_posters.poster_repository import PosterRepository

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = fetchall_return
        mock_conn   = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        repo = PosterRepository()
        with patch('mysql.connector.connect', return_value=mock_conn):
            result = repo.get_openai_completed_film_ids()

        return result, mock_cursor

    def test_returns_set_of_film_ids(self):
        result, _ = self._make_repo_call([(1,), (5,), (42,)])
        assert result == {1, 5, 42}

    def test_returns_empty_set_when_none(self):
        result, _ = self._make_repo_call([])
        assert result == set()

    def test_query_filters_by_provider_openai(self):
        _, cursor = self._make_repo_call([])
        sql = cursor.execute.call_args[0][0].lower()
        assert 'openai' in sql

    def test_query_filters_by_status_completed(self):
        _, cursor = self._make_repo_call([])
        sql = cursor.execute.call_args[0][0].lower()
        assert 'completed' in sql


# ── 5. Single-film mode (_run_single_film) ────────────────────────────

class TestRunSingleFilm:

    def _make_args(self, film_id: int = 1, dry_run: bool = False) -> argparse.Namespace:
        return argparse.Namespace(film_id=film_id, dry_run=dry_run, limit=5)

    def _make_service(self, poster_id: int = 42) -> MagicMock:
        svc = MagicMock()
        svc.generate.return_value = poster_id
        svc.get_poster_url.return_value = f'/posters/{poster_id:06d}.webp'
        return svc

    def test_film_not_found_exits_with_error(self):
        from scripts.generate_movie_posters import _run_single_film
        repo = MagicMock()

        with patch('scripts.generate_movie_posters._fetch_film_by_id', return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                _run_single_film(self._make_args(film_id=9999), service=None, repository=repo)

        assert exc_info.value.code == 1

    def test_dry_run_does_not_call_service(self):
        from scripts.generate_movie_posters import _run_single_film
        service = self._make_service()
        repo    = MagicMock()

        with patch('scripts.generate_movie_posters._fetch_film_by_id',
                   return_value=_make_film()):
            _run_single_film(self._make_args(dry_run=True), service=service, repository=repo)

        service.generate.assert_not_called()

    def test_skip_when_openai_poster_exists(self):
        from scripts.generate_movie_posters import _run_single_film
        service = self._make_service()
        repo    = MagicMock()
        repo.openai_poster_exists.return_value = True

        with patch('scripts.generate_movie_posters._fetch_film_by_id',
                   return_value=_make_film()):
            _run_single_film(self._make_args(), service=service, repository=repo)

        service.generate.assert_not_called()

    def test_generates_when_no_openai_poster(self):
        from scripts.generate_movie_posters import _run_single_film
        service = self._make_service()
        repo    = MagicMock()
        repo.openai_poster_exists.return_value = False

        with patch('scripts.generate_movie_posters._fetch_film_by_id',
                   return_value=_make_film()):
            _run_single_film(self._make_args(), service=service, repository=repo)

        service.generate.assert_called_once()

    def test_correct_description_passed_to_service(self):
        """When description exists, the real description must reach service.generate()."""
        from scripts.generate_movie_posters import _run_single_film
        service = self._make_service()
        repo    = MagicMock()
        repo.openai_poster_exists.return_value = False
        film = _make_film(description='An epic adventure across the ocean.')

        with patch('scripts.generate_movie_posters._fetch_film_by_id', return_value=film):
            _run_single_film(self._make_args(), service=service, repository=repo)

        kwargs = service.generate.call_args.kwargs
        assert kwargs['description'] == 'An epic adventure across the ocean.'

    def test_fallback_description_passed_when_empty(self):
        """When description is None, the fallback (title+genre) must reach service."""
        from scripts.generate_movie_posters import _run_single_film
        service = self._make_service()
        repo    = MagicMock()
        repo.openai_poster_exists.return_value = False
        film = _make_film(description=None, title='MY FILM', genre='Comedy')

        with patch('scripts.generate_movie_posters._fetch_film_by_id', return_value=film):
            _run_single_film(self._make_args(), service=service, repository=repo)

        kwargs = service.generate.call_args.kwargs
        assert 'MY FILM' in kwargs['description']

    def test_provider_error_exits_with_code_1(self):
        from scripts.generate_movie_posters import _run_single_film
        from services.ai_posters.exceptions import ProviderError
        service = self._make_service()
        service.generate.side_effect = ProviderError("API failure", provider="openai")
        repo    = MagicMock()
        repo.openai_poster_exists.return_value = False

        with patch('scripts.generate_movie_posters._fetch_film_by_id',
                   return_value=_make_film()):
            with pytest.raises(SystemExit) as exc_info:
                _run_single_film(self._make_args(), service=service, repository=repo)

        assert exc_info.value.code == 1

    def test_film_id_passed_to_service(self):
        """The correct film_id from Sakila must reach service.generate()."""
        from scripts.generate_movie_posters import _run_single_film
        service = self._make_service()
        repo    = MagicMock()
        repo.openai_poster_exists.return_value = False
        film = _make_film(film_id=77)

        with patch('scripts.generate_movie_posters._fetch_film_by_id', return_value=film):
            _run_single_film(self._make_args(film_id=77), service=service, repository=repo)

        kwargs = service.generate.call_args.kwargs
        assert kwargs['film_id'] == 77


# ── 6. Batch mode (_run_batch) ────────────────────────────────────────

class TestRunBatch:

    def _make_args(self, limit: int = 2, dry_run: bool = False) -> argparse.Namespace:
        return argparse.Namespace(film_id=None, dry_run=dry_run, limit=limit)

    def _make_service(self) -> MagicMock:
        svc = MagicMock()
        svc.generate.return_value = 99
        svc.get_poster_url.return_value = '/posters/test.webp'
        return svc

    def _run(
        self,
        args: argparse.Namespace,
        films: list[dict],
        pending_batches: list[list[dict]],
        openai_done_ids: set[int] | None = None,
        openai_exists_map: dict | None = None,
        generate_side_effect=None,
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        from scripts.generate_movie_posters import _run_batch

        service    = self._make_service()
        if generate_side_effect is not None:
            service.generate.side_effect = generate_side_effect

        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = openai_done_ids or set()
        if openai_exists_map:
            repository.openai_poster_exists.side_effect = (
                lambda fid: openai_exists_map.get(fid, False)
            )
        else:
            repository.openai_poster_exists.return_value = False

        queue = MagicMock()
        queue.get_pending.side_effect = pending_batches + [[]]
        queue.get_stats.return_value = {}
        queue.bulk_enqueue.return_value = 0

        with patch('scripts.generate_movie_posters._fetch_films', return_value=films):
            with patch('scripts.generate_movie_posters._reset_stuck_processing', return_value=0):
                _run_batch(args, service=service, repository=repository, queue=queue)

        return service, repository, queue

    # ── limit ──────────────────────────────────────────────────────────

    def test_limit_stops_after_n_generated(self):
        """With limit=2 and 3 pending films, only 2 must be generated."""
        films = [_make_film(i, title=f'FILM {i}') for i in range(1, 4)]
        pending = [[_make_queue_item(i, i * 10) for i in range(1, 4)]]

        service, _, _ = self._run(self._make_args(limit=2), films, pending)

        assert service.generate.call_count == 2

    def test_limit_1_generates_exactly_one(self):
        films = [_make_film(i, title=f'FILM {i}') for i in range(1, 6)]
        pending = [[_make_queue_item(i, i * 10) for i in range(1, 6)]]

        service, _, _ = self._run(self._make_args(limit=1), films, pending)

        assert service.generate.call_count == 1

    # ── error handling ─────────────────────────────────────────────────

    def test_error_on_first_film_does_not_stop_second(self):
        """A failed generation must not stop the batch — next film is still attempted."""
        films = [_make_film(1, title='FAIL FILM'), _make_film(2, title='OK FILM')]
        pending = [[_make_queue_item(1, 10), _make_queue_item(2, 20)]]

        service, _, queue = self._run(
            self._make_args(limit=2),
            films,
            pending,
            generate_side_effect=[Exception("timeout"), 77],
        )

        assert service.generate.call_count == 2
        queue.mark_failed.assert_called()
        queue.mark_done.assert_called()

    def test_failed_item_queue_status_is_failed(self):
        """mark_failed must be called for the failing item."""
        films   = [_make_film(1)]
        pending = [[_make_queue_item(1, 10)]]

        _, _, queue = self._run(
            self._make_args(limit=1),
            films,
            pending,
            generate_side_effect=Exception("API error"),
        )

        queue.mark_failed.assert_called_with(10)

    # ── skip logic ─────────────────────────────────────────────────────

    def test_skip_does_not_count_toward_limit(self):
        """
        Film 1 has an OpenAI poster → skip (no limit decrement).
        Film 2 does not → generate → limit=1 satisfied.
        Only film 2 must be generated.
        """
        films   = [_make_film(1, title='DONE FILM'), _make_film(2, title='NEW FILM')]
        pending = [[_make_queue_item(1, 10), _make_queue_item(2, 20)]]

        service, _, _ = self._run(
            self._make_args(limit=1),
            films,
            pending,
            openai_done_ids={1},
            openai_exists_map={1: True, 2: False},
        )

        assert service.generate.call_count == 1
        assert service.generate.call_args.kwargs['film_id'] == 2

    def test_mock_poster_does_not_prevent_generation(self):
        """openai_poster_exists must return False for mock-posterized films."""
        films   = [_make_film(1)]
        pending = [[_make_queue_item(1, 10)]]

        # Simulate: film 1 has a mock poster but no OpenAI poster
        service, _, _ = self._run(
            self._make_args(limit=1),
            films,
            pending,
            openai_exists_map={1: False},   # openai_poster_exists returns False
        )

        service.generate.assert_called_once()

    def test_skipped_film_queue_item_marked_done(self):
        """When a film is skipped, its queue item must be marked done."""
        films   = [_make_film(1)]
        pending = [[_make_queue_item(1, 10)]]

        _, _, queue = self._run(
            self._make_args(limit=5),
            films,
            pending,
            openai_exists_map={1: True},
        )

        queue.mark_done.assert_called_with(10)

    # ── dry-run ────────────────────────────────────────────────────────

    def test_dry_run_does_not_call_service(self):
        from scripts.generate_movie_posters import _run_batch

        films      = [_make_film(1)]
        service    = self._make_service()
        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = set()
        queue = MagicMock()
        queue.get_pending.return_value = [_make_queue_item(1)]
        queue.bulk_enqueue.return_value = 0

        with patch('scripts.generate_movie_posters._fetch_films', return_value=films):
            with patch('scripts.generate_movie_posters._reset_stuck_processing', return_value=0):
                _run_batch(
                    self._make_args(dry_run=True),
                    service=service,
                    repository=repository,
                    queue=queue,
                )

        service.generate.assert_not_called()

    # ── queue interaction ──────────────────────────────────────────────

    def test_mark_processing_called_before_generate(self):
        """queue.mark_processing must be called before service.generate."""
        films   = [_make_film(1)]
        pending = [[_make_queue_item(1, 10)]]
        call_order = []

        from scripts.generate_movie_posters import _run_batch
        service    = self._make_service()
        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = set()
        repository.openai_poster_exists.return_value = False
        queue = MagicMock()
        queue.get_pending.side_effect = [pending[0], []]
        queue.get_stats.return_value = {}
        queue.bulk_enqueue.return_value = 0

        def _mark_proc(qid):
            call_order.append('mark_processing')
        def _generate(**kw):
            call_order.append('generate')
            return 1
        queue.mark_processing.side_effect = _mark_proc
        service.generate.side_effect = _generate

        with patch('scripts.generate_movie_posters._fetch_films', return_value=films):
            with patch('scripts.generate_movie_posters._reset_stuck_processing', return_value=0):
                _run_batch(
                    self._make_args(limit=1),
                    service=service,
                    repository=repository,
                    queue=queue,
                )

        assert call_order == ['mark_processing', 'generate']

    def test_missing_film_id_in_lookup_marks_failed(self):
        """Queue item whose film_id is not in Sakila must be marked failed."""
        films   = [_make_film(1)]  # Only film 1 in Sakila
        pending = [[_make_queue_item(999, 50)]]   # film 999 not in Sakila

        service, _, queue = self._run(
            self._make_args(limit=1),
            films,
            pending,
        )

        queue.mark_failed.assert_called_with(50)
        service.generate.assert_not_called()


# ── 7. --dry-run contract: must be fully read-only ────────────────────

class TestDryRunSafety:
    """
    Verify that --dry-run is a true no-op with respect to DB writes,
    file creation, and API calls.
    """

    # ── shared helpers ─────────────────────────────────────────────────

    def _batch_dry_run(
        self,
        films: list[dict],
        openai_done_ids: set | None = None,
        limit: int = 5,
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        """
        Call _run_batch with dry_run=True and return (service, repository, queue) mocks.
        _fetch_films is patched so no real DB connection is made.
        """
        from scripts.generate_movie_posters import _run_batch

        args       = argparse.Namespace(dry_run=True, film_id=None, limit=limit)
        service    = MagicMock()
        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = openai_done_ids or set()
        queue      = MagicMock()

        with patch('scripts.generate_movie_posters._fetch_films', return_value=films):
            _run_batch(args, service=service, repository=repository, queue=queue)

        return service, repository, queue

    def _parse(self, argv: list[str]) -> argparse.Namespace:
        from scripts.generate_movie_posters import parse_args
        with patch('sys.argv', ['script'] + argv):
            return parse_args()

    # ── Tests 1–7: batch dry-run is read-only ──────────────────────────

    def test_batch_dry_run_does_not_create_openai_provider(self):
        """OpenAIProvider must never be instantiated in dry-run mode."""
        with patch('scripts.generate_movie_posters.OpenAIProvider') as mock_cls:
            self._batch_dry_run([_make_film(1)])
        mock_cls.assert_not_called()

    def test_batch_dry_run_does_not_call_service(self):
        """PosterService.generate must not be called in dry-run mode."""
        service, _, _ = self._batch_dry_run([_make_film(1)])
        service.generate.assert_not_called()

    def test_batch_dry_run_does_not_call_repository_create_table(self):
        """repository.create_table must not be called in dry-run mode."""
        _, repository, _ = self._batch_dry_run([_make_film(1)])
        repository.create_table.assert_not_called()

    def test_batch_dry_run_does_not_call_queue_create_table(self):
        """queue.create_table must not be called in dry-run mode."""
        _, _, queue = self._batch_dry_run([_make_film(1)])
        queue.create_table.assert_not_called()

    def test_batch_dry_run_does_not_call_bulk_enqueue(self):
        """queue.bulk_enqueue must not be called in dry-run mode."""
        _, _, queue = self._batch_dry_run([_make_film(1)])
        queue.bulk_enqueue.assert_not_called()

    def test_batch_dry_run_does_not_call_reset_stuck_processing(self):
        """_reset_stuck_processing must not be called in dry-run mode."""
        with patch('scripts.generate_movie_posters._reset_stuck_processing') as mock_reset:
            self._batch_dry_run([_make_film(1)])
        mock_reset.assert_not_called()

    def test_batch_dry_run_does_not_call_any_mark_method(self):
        """No queue status changes are allowed in dry-run mode."""
        _, _, queue = self._batch_dry_run([_make_film(1)])
        queue.mark_processing.assert_not_called()
        queue.mark_done.assert_not_called()
        queue.mark_failed.assert_not_called()

    def test_batch_dry_run_does_not_create_files(self):
        """service.generate (which calls storage.save) must not run in dry-run."""
        service, _, _ = self._batch_dry_run([_make_film(1)])
        service.generate.assert_not_called()

    # ── Tests 8–9: single-film dry-run ────────────────────────────────

    def test_single_film_dry_run_does_not_call_api(self):
        """service.generate must not be called in single-film dry-run mode."""
        from scripts.generate_movie_posters import _run_single_film
        service = MagicMock()

        with patch('scripts.generate_movie_posters._fetch_film_by_id',
                   return_value=_make_film()):
            _run_single_film(
                argparse.Namespace(film_id=1, dry_run=True, limit=5),
                service=service,
                repository=MagicMock(),
            )

        service.generate.assert_not_called()

    def test_single_film_dry_run_builds_prompt_from_title_genre_description(self):
        """build_prompt must be called with real title, genre, description in dry-run."""
        from scripts.generate_movie_posters import _run_single_film
        film = _make_film(title='UNIQUE TITLE', genre='Thriller', description='Dark mystery.')

        with patch('scripts.generate_movie_posters._fetch_film_by_id', return_value=film):
            with patch('scripts.generate_movie_posters.build_prompt',
                       return_value=('prompt', 'negative')) as mock_build:
                _run_single_film(
                    argparse.Namespace(film_id=1, dry_run=True, limit=5),
                    service=None,
                    repository=MagicMock(),
                )

        mock_build.assert_called_once_with(
            title='UNIQUE TITLE',
            genre='Thriller',
            description='Dark mystery.',
            style='auto',
        )

    # ── Tests 10–13: argument validation ─────────────────────────────

    def test_limit_zero_is_rejected(self):
        """--limit 0 must be rejected by argparse before any DB connection."""
        with pytest.raises(SystemExit) as exc_info:
            self._parse(['--limit', '0'])
        assert exc_info.value.code != 0

    def test_limit_negative_is_rejected(self):
        """--limit -1 must be rejected by argparse before any DB connection."""
        with pytest.raises(SystemExit) as exc_info:
            self._parse(['--limit', '-1'])
        assert exc_info.value.code != 0

    def test_film_id_zero_is_rejected(self):
        """--film-id 0 must be rejected by argparse before any DB connection."""
        with pytest.raises(SystemExit) as exc_info:
            self._parse(['--film-id', '0'])
        assert exc_info.value.code != 0

    def test_film_id_negative_is_rejected(self):
        """--film-id -5 must be rejected by argparse before any DB connection."""
        with pytest.raises(SystemExit) as exc_info:
            self._parse(['--film-id', '-5'])
        assert exc_info.value.code != 0


# ── 8. Queue sync: GenerationQueue.sync_for_openai_generation ────────

class TestQueueSync:
    """
    Tests for GenerationQueue.sync_for_openai_generation(),
    retry_failed(), get_pending() ordering, and the --retry-failed CLI flag.
    """

    # ── helper ────────────────────────────────────────────────────────

    @staticmethod
    def _call_sync(
        film_ids: list[int],
        openai_done_ids: set[int],
        existing_queue: dict[int, str | tuple[str, int]],
        processing_timeout_minutes: int = 30,
    ) -> tuple[dict, MagicMock]:
        """
        Call sync_for_openai_generation with a fully mocked DB connection.

        existing_queue values may be:
          'pending'           → str shorthand (age_minutes defaults to 0)
          ('processing', 45)  → tuple (status, age_minutes) for processing tests
        """
        from services.ai_posters.queue import GenerationQueue

        existing_rows = []
        for fid, value in existing_queue.items():
            if isinstance(value, tuple):
                status, age = value
            else:
                status, age = value, 0
            existing_rows.append({'film_id': fid, 'status': status, 'age_minutes': age})

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = existing_rows
        mock_conn   = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        q = GenerationQueue()
        with patch('mysql.connector.connect', return_value=mock_conn):
            result = q.sync_for_openai_generation(
                film_ids, openai_done_ids,
                processing_timeout_minutes=processing_timeout_minutes,
            )

        return result, mock_cursor

    # ── Tests 1–6: sync status rules ──────────────────────────────────

    def test_done_without_openai_set_to_pending(self):
        """queue='done' (from MockProvider) but no OpenAI poster → pending."""
        result, _ = self._call_sync(
            film_ids=[10],
            openai_done_ids=set(),
            existing_queue={10: 'done'},
        )
        assert result['set_to_pending'] == 1
        assert result['unchanged']      == 0

    def test_failed_without_openai_remains_failed(self):
        """queue='failed' and no OpenAI poster → unchanged (use --retry-failed)."""
        result, _ = self._call_sync(
            film_ids=[7],
            openai_done_ids=set(),
            existing_queue={7: 'failed'},
        )
        assert result['unchanged']      == 1
        assert result['set_to_pending'] == 0

    def test_pending_without_openai_unchanged(self):
        """queue='pending' and no OpenAI poster → unchanged."""
        result, _ = self._call_sync(
            film_ids=[5],
            openai_done_ids=set(),
            existing_queue={5: 'pending'},
        )
        assert result['unchanged']      == 1
        assert result['set_to_pending'] == 0

    def test_completed_openai_set_to_done(self):
        """Completed OpenAI poster + queue='pending' → done."""
        result, _ = self._call_sync(
            film_ids=[1],
            openai_done_ids={1},
            existing_queue={1: 'pending'},
        )
        assert result['set_to_done']    == 1
        assert result['set_to_pending'] == 0
        assert result['unchanged']      == 0

    def test_fresh_processing_remains_processing(self):
        """queue='processing' with age < timeout → unchanged (still active)."""
        result, _ = self._call_sync(
            film_ids=[3],
            openai_done_ids=set(),
            existing_queue={3: ('processing', 5)},   # 5 minutes old
            processing_timeout_minutes=30,
        )
        assert result['unchanged']      == 1
        assert result['set_to_pending'] == 0

    def test_stale_processing_reset_to_pending(self):
        """queue='processing' with age >= timeout → pending (stuck run)."""
        result, _ = self._call_sync(
            film_ids=[3],
            openai_done_ids=set(),
            existing_queue={3: ('processing', 45)},  # 45 minutes old
            processing_timeout_minutes=30,
        )
        assert result['set_to_pending'] == 1
        assert result['unchanged']      == 0

    # ── Additional sync correctness tests ─────────────────────────────

    def test_missing_queue_item_inserted_as_pending(self):
        """No queue entry and no OpenAI poster → INSERT pending."""
        result, cursor = self._call_sync(
            film_ids=[99],
            openai_done_ids=set(),
            existing_queue={},
        )
        assert result['inserted']       == 1
        assert result['set_to_pending'] == 0
        sql_calls = [str(c) for c in cursor.executemany.call_args_list]
        assert any('pending' in s for s in sql_calls)

    def test_already_done_with_openai_unchanged(self):
        """queue='done' and has completed OpenAI poster → unchanged."""
        result, _ = self._call_sync(
            film_ids=[1],
            openai_done_ids={1},
            existing_queue={1: 'done'},
        )
        assert result['unchanged']   == 1
        assert result['set_to_done'] == 0

    def test_mixed_batch_counts_are_correct(self):
        """All four counters for a batch that includes a failed film."""
        # film 1: OpenAI done + queue='done'    → unchanged
        # film 2: OpenAI done + queue='pending' → set_to_done
        # film 3: no OpenAI  + queue='done'    → set_to_pending (was mock)
        # film 4: no OpenAI  + queue='pending' → unchanged
        # film 5: no OpenAI  + not in queue    → inserted pending
        # film 6: no OpenAI  + queue='failed'  → unchanged (leave failed)
        result, _ = self._call_sync(
            film_ids=[1, 2, 3, 4, 5, 6],
            openai_done_ids={1, 2},
            existing_queue={
                1: 'done', 2: 'pending', 3: 'done', 4: 'pending', 6: 'failed',
            },
        )
        assert result['unchanged']      == 3   # film 1, film 4, film 6
        assert result['set_to_done']    == 1   # film 2
        assert result['set_to_pending'] == 1   # film 3
        assert result['inserted']       == 1   # film 5

    def test_empty_film_ids_returns_zeros(self):
        """Empty input must return all zeros without touching the DB."""
        from services.ai_posters.queue import GenerationQueue
        q      = GenerationQueue()
        result = q.sync_for_openai_generation([], set())
        assert result == {'inserted': 0, 'set_to_pending': 0, 'set_to_done': 0, 'unchanged': 0}

    # ── Test 7: live batch does not auto-retry failed ─────────────────

    def test_live_batch_does_not_retry_failed_items(self):
        """
        After sync, a failed film without OpenAI poster stays failed.
        It must NOT appear in get_pending() and must NOT be generated.
        """
        from scripts.generate_movie_posters import _run_batch

        films   = [_make_film(10), _make_film(11)]
        service = MagicMock()
        service.generate.return_value = 99
        service.get_poster_url.return_value = '/posters/test.webp'

        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = set()
        repository.openai_poster_exists.return_value = False

        queue = MagicMock()
        # Sync leaves film 10 failed (unchanged), film 11 stays pending
        queue.sync_for_openai_generation.return_value = {
            'inserted': 0, 'set_to_pending': 0, 'set_to_done': 0, 'unchanged': 2,
        }
        # get_pending only returns film 11 (film 10 is failed, not pending)
        queue.get_pending.side_effect = [[_make_queue_item(11, 20)], []]
        queue.get_stats.return_value = {'failed': 1, 'done': 1}

        with patch('scripts.generate_movie_posters._fetch_films', return_value=films):
            _run_batch(
                argparse.Namespace(dry_run=False, film_id=None, limit=5),
                service=service, repository=repository, queue=queue,
            )

        # film 10 was never generated
        for call in service.generate.call_args_list:
            assert call.kwargs['film_id'] != 10
        service.generate.assert_called_once()
        assert service.generate.call_args.kwargs['film_id'] == 11

    # ── Tests 8–11: --retry-failed CLI flag ───────────────────────────

    def test_retry_failed_film_id_resets_only_that_film(self):
        """--retry-failed --film-id 10 resets only film_id=10."""
        from scripts.generate_movie_posters import _run_retry_failed

        queue = MagicMock()
        queue.retry_failed.return_value = 1

        _run_retry_failed(
            argparse.Namespace(film_id=10, dry_run=False),
            queue,
        )

        queue.retry_failed.assert_called_once_with(film_id=10)

    def test_retry_failed_all_resets_all_failed(self):
        """--retry-failed without --film-id resets all failed items."""
        from scripts.generate_movie_posters import _run_retry_failed

        queue = MagicMock()
        queue.count_by_status.return_value = 3
        queue.retry_failed.return_value = 3

        _run_retry_failed(
            argparse.Namespace(film_id=None, dry_run=False),
            queue,
        )

        queue.retry_failed.assert_called_once_with()

    def test_retry_failed_does_not_create_openai_provider(self):
        """--retry-failed must not instantiate OpenAIProvider."""
        from scripts.generate_movie_posters import _run_retry_failed

        with patch('scripts.generate_movie_posters.OpenAIProvider') as mock_cls:
            queue = MagicMock()
            queue.count_by_status.return_value = 1
            queue.retry_failed.return_value = 1
            _run_retry_failed(argparse.Namespace(film_id=None), queue)

        mock_cls.assert_not_called()

    def test_retry_failed_does_not_call_service(self):
        """--retry-failed must not instantiate or call PosterService."""
        from scripts.generate_movie_posters import _run_retry_failed

        with patch('scripts.generate_movie_posters.PosterService') as mock_cls:
            queue = MagicMock()
            queue.count_by_status.return_value = 1
            queue.retry_failed.return_value = 1
            _run_retry_failed(argparse.Namespace(film_id=None), queue)

        mock_cls.assert_not_called()

    # ── Test 12: get_pending ordering ─────────────────────────────────

    def test_get_pending_orders_by_priority_desc_film_id_asc(self):
        """get_pending SQL must use priority DESC, film_id ASC (not created_at)."""
        from services.ai_posters.queue import GenerationQueue

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn   = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        q = GenerationQueue()
        with patch('mysql.connector.connect', return_value=mock_conn):
            q.get_pending(limit=10)

        sql = mock_cursor.execute.call_args[0][0].lower()
        assert 'priority desc' in sql
        assert 'film_id asc'   in sql
        assert 'created_at'    not in sql

    # ── Test 13: film_id=10 stays failed after sync ───────────────────

    def test_film_id_10_remains_failed_after_sync(self):
        """film_id=10 with 'failed' status and no OpenAI poster must stay failed."""
        result, _ = self._call_sync(
            film_ids=[10],
            openai_done_ids=set(),
            existing_queue={10: 'failed'},
        )
        assert result['unchanged']      == 1
        assert result['set_to_pending'] == 0

    # ── --sync-queue flag read-only tests (kept from previous session) ─

    def _run_sync_queue_with_mocks(self) -> tuple[MagicMock, MagicMock]:
        from scripts.generate_movie_posters import _run_sync_queue
        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = set()
        queue = MagicMock()
        queue.sync_for_openai_generation.return_value = {
            'inserted': 0, 'set_to_pending': 0, 'set_to_done': 0, 'unchanged': 0,
        }
        with patch('scripts.generate_movie_posters._fetch_films', return_value=[]):
            _run_sync_queue(repository, queue)
        return repository, queue

    def test_sync_queue_does_not_create_openai_provider(self):
        with patch('scripts.generate_movie_posters.OpenAIProvider') as mock_cls:
            self._run_sync_queue_with_mocks()
        mock_cls.assert_not_called()

    def test_sync_queue_does_not_call_service(self):
        with patch('scripts.generate_movie_posters.PosterService') as mock_cls:
            self._run_sync_queue_with_mocks()
        mock_cls.assert_not_called()

    def test_sync_queue_does_not_create_files(self):
        with patch('scripts.generate_movie_posters.PosterStorage') as mock_cls:
            self._run_sync_queue_with_mocks()
        mock_cls.assert_not_called()

    def test_sync_queue_does_not_write_to_movie_posters(self):
        repository, _ = self._run_sync_queue_with_mocks()
        repository.save.assert_not_called()

    def test_dry_run_does_not_call_sync_write(self):
        from scripts.generate_movie_posters import _run_batch
        queue      = MagicMock()
        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = set()
        with patch('scripts.generate_movie_posters._fetch_films',
                   return_value=[_make_film(1)]):
            _run_batch(
                argparse.Namespace(dry_run=True, film_id=None, limit=5),
                service=None, repository=repository, queue=queue,
            )
        queue.sync_for_openai_generation.assert_not_called()

    def test_live_batch_calls_sync_before_generation(self):
        from scripts.generate_movie_posters import _run_batch
        films   = [_make_film(1), _make_film(2)]
        service = MagicMock()
        service.generate.return_value = 99
        service.get_poster_url.return_value = '/posters/test.webp'
        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = set()
        repository.openai_poster_exists.return_value = False
        queue = MagicMock()
        queue.sync_for_openai_generation.return_value = {
            'inserted': 0, 'set_to_pending': 2, 'set_to_done': 0, 'unchanged': 0,
        }
        queue.get_pending.side_effect = [
            [_make_queue_item(1, 10), _make_queue_item(2, 20)], [],
        ]
        queue.get_stats.return_value = {}
        with patch('scripts.generate_movie_posters._fetch_films', return_value=films):
            _run_batch(
                argparse.Namespace(dry_run=False, film_id=None, limit=5),
                service=service, repository=repository, queue=queue,
            )
        queue.sync_for_openai_generation.assert_called_once()
        assert service.generate.call_count == 2

    def test_film_with_openai_poster_not_regenerated_in_batch(self):
        from scripts.generate_movie_posters import _run_batch
        films   = [_make_film(1), _make_film(2)]
        service = MagicMock()
        service.generate.return_value = 99
        service.get_poster_url.return_value = '/posters/test.webp'
        repository = MagicMock()
        repository.get_openai_completed_film_ids.return_value = {1}
        repository.openai_poster_exists.side_effect = lambda fid: fid == 1
        queue = MagicMock()
        queue.sync_for_openai_generation.return_value = {
            'inserted': 0, 'set_to_pending': 1, 'set_to_done': 0, 'unchanged': 1,
        }
        queue.get_pending.side_effect = [[_make_queue_item(2, 20)], []]
        queue.get_stats.return_value = {}
        with patch('scripts.generate_movie_posters._fetch_films', return_value=films):
            _run_batch(
                argparse.Namespace(dry_run=False, film_id=None, limit=5),
                service=service, repository=repository, queue=queue,
            )
        service.generate.assert_called_once()
        assert service.generate.call_args.kwargs['film_id'] == 2