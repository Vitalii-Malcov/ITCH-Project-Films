"""
GenerationQueue — manages the movie poster generation queue.

Responsibilities:
    - Create and manage the movie_generation_queue table.
    - Add films to the queue (enqueue).
    - Retrieve pending items in priority order for the generator script.
    - Track status transitions: pending → processing → done / failed.

What it does NOT do:
    - Generate images (that is PosterService's job).
    - Know about prompts, providers, or file storage.

Status lifecycle:
    pending     — waiting to be picked up by the generator
    processing  — currently being generated (avoids duplicate work)
    done        — successfully completed
    failed      — generation failed (tries counter incremented)

Priority:
    Higher number = processed first.
    Default = 5. Use priority=10 for urgent re-runs.
    Within the same priority, older items are processed first (FIFO).
"""

import os
import sys
import logging

import mysql.connector

from services.ai_posters.exceptions import RepositoryError

logger = logging.getLogger(__name__)

# ── sys.path setup ────────────────────────────────────────────────────
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_itch_films = os.path.join(_project_root, 'itch_films')
if _itch_films not in sys.path:
    sys.path.insert(0, _itch_films)

import local_settings  # noqa: E402

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movie_generation_queue (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    film_id    INT NOT NULL UNIQUE,
    priority   INT          DEFAULT 5,
    status     VARCHAR(50)  DEFAULT 'pending',
    tries      INT          DEFAULT 0,
    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status   (status),
    INDEX idx_priority (priority)
)
"""


class GenerationQueue:
    """Manages the movie poster generation queue in the write database."""

    # ── Connection ────────────────────────────────────────────────────

    def _connect(self):
        try:
            return mysql.connector.connect(**local_settings.dbconfig_write)
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: cannot connect to write database.",
                details=str(exc),
            ) from exc

    # ── DDL ───────────────────────────────────────────────────────────

    def create_table(self) -> None:
        """Create movie_generation_queue table if it does not exist."""
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(_CREATE_TABLE_SQL)
            conn.commit()
            logger.info("movie_generation_queue table is ready.")
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: failed to create table.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    # ── Write ─────────────────────────────────────────────────────────

    def enqueue(self, film_id: int, priority: int = 5) -> None:
        """
        Add a film to the queue if it is not already present.

        INSERT IGNORE respects the UNIQUE constraint on film_id —
        a film already in the queue (any status) is silently skipped.
        This makes enqueue safe to call multiple times for the same film.
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT IGNORE INTO movie_generation_queue "
                "(film_id, priority) VALUES (%s, %s)",
                (film_id, priority),
            )
            conn.commit()
            if cursor.rowcount:
                logger.debug(f"Enqueued film_id={film_id} priority={priority}")
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"Queue: failed to enqueue film_id={film_id}.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def bulk_enqueue(self, film_ids: list[int], priority: int = 5) -> int:
        """
        Add multiple films to the queue in a single INSERT statement.

        Returns the number of newly added rows (duplicates are ignored).
        Use this instead of calling enqueue() in a loop to avoid N round-trips.
        """
        if not film_ids:
            return 0
        conn = self._connect()
        cursor = conn.cursor()
        try:
            values = [(fid, priority) for fid in film_ids]
            cursor.executemany(
                "INSERT IGNORE INTO movie_generation_queue "
                "(film_id, priority) VALUES (%s, %s)",
                values,
            )
            conn.commit()
            inserted = cursor.rowcount
            logger.debug(f"bulk_enqueue: {inserted} new items from {len(film_ids)} films")
            return inserted
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: bulk_enqueue failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def mark_processing(self, queue_id: int) -> None:
        """Mark a queue item as currently being processed."""
        self._update_status(queue_id, 'processing')

    def mark_done(self, queue_id: int) -> None:
        """Mark a queue item as successfully completed."""
        self._update_status(queue_id, 'done')

    def mark_failed(self, queue_id: int) -> None:
        """Mark a queue item as failed and increment the tries counter."""
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE movie_generation_queue "
                "SET status = 'failed', tries = tries + 1 "
                "WHERE id = %s",
                (queue_id,),
            )
            conn.commit()
            logger.warning(f"Queue item id={queue_id} marked as failed.")
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"Queue: failed to mark item {queue_id} as failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    # ── Read ──────────────────────────────────────────────────────────

    def get_pending(self, limit: int = 10) -> list[dict]:
        """
        Return up to `limit` pending queue items.

        Ordered by priority DESC (higher number = processed first),
        then by film_id ASC (predictable, repeatable order within the same priority).
        """
        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT * FROM movie_generation_queue "
                "WHERE status = 'pending' "
                "ORDER BY priority DESC, film_id ASC "
                "LIMIT %s",
                (limit,),
            )
            return cursor.fetchall()
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: failed to fetch pending items.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def get_stats(self) -> dict[str, int]:
        """
        Return item counts grouped by status.
        Example: {'pending': 5, 'done': 100, 'failed': 2}
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT status, COUNT(*) "
                "FROM movie_generation_queue "
                "GROUP BY status"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: failed to fetch stats.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def sync_for_openai_generation(
        self,
        all_film_ids: list[int],
        completed_openai_film_ids: set[int],
        processing_timeout_minutes: int = 30,
    ) -> dict[str, int]:
        """
        Synchronise the queue against completed OpenAI posters (source of truth).

        Per-status rules for films WITHOUT a completed OpenAI poster:
          'done'       → 'pending'   (was completed by MockProvider; needs real generation)
          'pending'    → unchanged   (already waiting; do not disturb)
          'failed'     → unchanged   (explicit error; use --retry-failed to re-queue)
          'processing' → 'pending' only if age_minutes >= processing_timeout_minutes
                         (stuck from a crashed run); otherwise unchanged
          missing      → INSERT 'pending'

        For films WITH a completed OpenAI poster:
          any status   → 'done' (or unchanged if already 'done')
          missing      → INSERT 'done'

        tries and created_at of existing rows are preserved.

        Returns:
            {
              'inserted':       new queue entries created,
              'set_to_pending': existing entries changed to 'pending',
              'set_to_done':    existing entries changed to 'done',
              'unchanged':      entries left at their current status,
            }
        """
        if not all_film_ids:
            return {'inserted': 0, 'set_to_pending': 0, 'set_to_done': 0, 'unchanged': 0}

        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        try:
            # Fetch current queue state plus age for processing detection
            placeholders = ', '.join(['%s'] * len(all_film_ids))
            cursor.execute(
                f"SELECT film_id, status, "
                f"TIMESTAMPDIFF(MINUTE, created_at, NOW()) AS age_minutes "
                f"FROM movie_generation_queue "
                f"WHERE film_id IN ({placeholders})",
                all_film_ids,
            )
            existing: dict[int, dict] = {
                row['film_id']: row for row in cursor.fetchall()
            }

            to_insert_pending = []
            to_insert_done    = []
            to_set_pending    = []
            to_set_done       = []
            unchanged         = 0

            for fid in all_film_ids:
                row = existing.get(fid)

                if fid in completed_openai_film_ids:
                    # Film has a completed OpenAI poster → must be 'done'
                    if row is None:
                        to_insert_done.append(fid)
                    elif row['status'] == 'done':
                        unchanged += 1
                    else:
                        to_set_done.append(fid)
                else:
                    # No completed OpenAI poster — per-status rules
                    if row is None:
                        to_insert_pending.append(fid)
                    elif row['status'] == 'done':
                        to_set_pending.append(fid)       # was mock-done; re-queue
                    elif row['status'] == 'pending':
                        unchanged += 1
                    elif row['status'] == 'failed':
                        unchanged += 1                   # leave; use --retry-failed
                    elif row['status'] == 'processing':
                        age = row.get('age_minutes') or 0
                        if age >= processing_timeout_minutes:
                            to_set_pending.append(fid)   # stuck run; reset
                        else:
                            unchanged += 1               # still active; leave it

            if to_insert_pending:
                cursor.executemany(
                    "INSERT INTO movie_generation_queue (film_id, priority, status) "
                    "VALUES (%s, 5, 'pending')",
                    [(fid,) for fid in to_insert_pending],
                )

            if to_insert_done:
                cursor.executemany(
                    "INSERT INTO movie_generation_queue (film_id, priority, status) "
                    "VALUES (%s, 5, 'done')",
                    [(fid,) for fid in to_insert_done],
                )

            if to_set_pending:
                ph = ', '.join(['%s'] * len(to_set_pending))
                cursor.execute(
                    f"UPDATE movie_generation_queue SET status = 'pending' "
                    f"WHERE film_id IN ({ph})",
                    to_set_pending,
                )

            if to_set_done:
                ph = ', '.join(['%s'] * len(to_set_done))
                cursor.execute(
                    f"UPDATE movie_generation_queue SET status = 'done' "
                    f"WHERE film_id IN ({ph})",
                    to_set_done,
                )

            conn.commit()

            inserted = len(to_insert_pending) + len(to_insert_done)
            logger.info(
                "Queue sync: inserted=%d set_pending=%d set_done=%d unchanged=%d",
                inserted, len(to_set_pending), len(to_set_done), unchanged,
            )

            return {
                'inserted':       inserted,
                'set_to_pending': len(to_set_pending),
                'set_to_done':    len(to_set_done),
                'unchanged':      unchanged,
            }

        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: sync_for_openai_generation failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def retry_failed(self, film_id: int | None = None) -> int:
        """
        Reset failed queue items to 'pending' for explicit retry.

        If film_id is provided: only that film is reset.
        Otherwise: all failed items are reset.
        Returns the number of items changed.
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            if film_id is not None:
                cursor.execute(
                    "UPDATE movie_generation_queue SET status = 'pending' "
                    "WHERE film_id = %s AND status = 'failed'",
                    (film_id,),
                )
            else:
                cursor.execute(
                    "UPDATE movie_generation_queue SET status = 'pending' "
                    "WHERE status = 'failed'"
                )
            count = cursor.rowcount
            conn.commit()
            logger.info("retry_failed: %d item(s) reset to pending (film_id=%s)", count, film_id)
            return count
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: retry_failed failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def count_by_status(self, status: str) -> int:
        """Return the number of queue items with the given status."""
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM movie_generation_queue WHERE status = %s",
                (status,),
            )
            return cursor.fetchone()[0]
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"Queue: count_by_status('{status}') failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    # ── Private helper ────────────────────────────────────────────────

    def _update_status(self, queue_id: int, status: str) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE movie_generation_queue SET status = %s WHERE id = %s",
                (status, queue_id),
            )
            conn.commit()
            logger.debug(f"Queue item id={queue_id} → {status}")
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"Queue: failed to set status={status} for id={queue_id}.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()