"""
GenerationQueue — управляет очередью генерации постеров фильмов.

Обязанности:
    - Создавать и обслуживать таблицу movie_generation_queue.
    - Добавлять фильмы в очередь (enqueue).
    - Извлекать ожидающие элементы в порядке приоритета для скрипта-генератора.
    - Отслеживать переходы статуса: pending → processing → done / failed.

Чего НЕ делает:
    - Не генерирует изображения (это задача PosterService).
    - Не знает про промпты, провайдеров или файловое хранилище.

Жизненный цикл статуса:
    pending     — ожидает, пока генератор не заберёт задачу
    processing  — сейчас генерируется (избегает дублирования работы)
    done        — успешно завершено
    failed      — генерация не удалась (счётчик tries увеличивается)

Приоритет:
    Чем выше число — тем раньше обрабатывается.
    По умолчанию = 5. Используйте priority=10 для срочных перегенераций.
    В рамках одного приоритета более старые элементы обрабатываются первыми (FIFO).
"""

import os
import sys
import logging

import mysql.connector

from services.ai_posters.exceptions import RepositoryError

logger = logging.getLogger(__name__)

# ── Настройка sys.path ────────────────────────────────────────────────────
# dirname × 3 от __file__ — это корень itch_films_OOP/ (services/ai_posters/
# живёт внутри проекта, а не в корне репозитория — доп. join(..., 'itch_films')
# тут не нужен, см. подробный комментарий в poster_repository.py).
_itch_films = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _itch_films in sys.path:
    sys.path.remove(_itch_films)
sys.path.insert(0, _itch_films)

import local_settings  # noqa: E402

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS movie_generation_queue (
    id                     INT AUTO_INCREMENT PRIMARY KEY,
    film_id                INT NOT NULL UNIQUE,
    priority               INT          DEFAULT 5,
    status                 VARCHAR(50)  DEFAULT 'pending',
    tries                  INT          DEFAULT 0,
    created_at             TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    processing_started_at  TIMESTAMP    NULL,
    claim_token            INT          NOT NULL DEFAULT 0,
    INDEX idx_status   (status),
    INDEX idx_priority (priority)
)
"""

# Таблица могла быть создана раньше, до появления этих колонок
# (CREATE TABLE IF NOT EXISTS её не тронет) — добавляем колонки
# отдельным ALTER, если их ещё нет. MySQL 8.0.29+.
_ADD_PROCESSING_STARTED_AT_SQL = """
ALTER TABLE movie_generation_queue
ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMP NULL
"""

# claim_token — «fencing token»: увеличивается на 1 при каждом успешном
# захвате элемента через mark_processing(). mark_done()/mark_failed()
# принимают token, полученный при захвате, и применяют изменение, только
# если он всё ещё совпадает с текущим значением в БД. Без этого: если
# элемент по таймауту сброшен в pending и захвачен ЗАНОВО (другим
# запуском), а «старый» воркер после этого всё-таки достучится до API и
# вызовет mark_done()/mark_failed() — он тихо перезапишет статус нового,
# ещё выполняющегося захвата.
_ADD_CLAIM_TOKEN_SQL = """
ALTER TABLE movie_generation_queue
ADD COLUMN IF NOT EXISTS claim_token INT NOT NULL DEFAULT 0
"""


class GenerationQueue:
    """Управляет очередью генерации постеров фильмов в write-базе данных."""

    # ── Подключение ────────────────────────────────────────────────────

    def _connect(self):
        """Подключение из того же именованного пула, что и PosterRepository
        (одинаковый pool_name="itch_films_write" — mysql-connector-python
        переиспользует один и тот же пул соединений для обоих классов)."""
        try:
            return mysql.connector.connect(
                pool_name="itch_films_write",
                pool_size=5,
                **local_settings.dbconfig_write,
            )
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: cannot connect to write database.",
                details=str(exc),
            ) from exc

    # ── DDL ───────────────────────────────────────────────────────────

    def create_table(self) -> None:
        """
        Создаёт таблицу movie_generation_queue, если она не существует,
        и доводит схему существующей таблицы до актуальной (добавляет
        processing_started_at и claim_token, если их ещё нет — см.
        комментарии у _ADD_PROCESSING_STARTED_AT_SQL / _ADD_CLAIM_TOKEN_SQL выше).
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(_CREATE_TABLE_SQL)
            cursor.execute(_ADD_PROCESSING_STARTED_AT_SQL)
            cursor.execute(_ADD_CLAIM_TOKEN_SQL)
            conn.commit()
            logger.info("Таблица movie_generation_queue готова.")
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: failed to create table.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    # ── Запись ─────────────────────────────────────────────────────────

    def enqueue(self, film_id: int, priority: int = 5) -> None:
        """
        Добавляет фильм в очередь, если его там ещё нет.

        INSERT IGNORE учитывает ограничение UNIQUE на film_id —
        фильм, уже находящийся в очереди (в любом статусе), молча пропускается.
        Это делает enqueue безопасным для многократного вызова с одним и тем же фильмом.
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
                logger.debug(f"В очередь добавлен film_id={film_id} priority={priority}")
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
        Добавляет несколько фильмов в очередь одним INSERT-запросом.

        Возвращает количество новых добавленных строк (дубли игнорируются).
        Используйте вместо вызова enqueue() в цикле, чтобы избежать N round-trip'ов.
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
            logger.debug(f"bulk_enqueue: {inserted} новых записей из {len(film_ids)} фильмов")
            return inserted
        except mysql.connector.Error as exc:
            raise RepositoryError(
                "Queue: bulk_enqueue failed.",
                details=str(exc),
            ) from exc
        finally:
            cursor.close()
            conn.close()

    def mark_processing(self, queue_id: int) -> int | None:
        """
        Пытается атомарно захватить элемент очереди для обработки.

        Условие `AND status = 'pending'` в UPDATE — это и есть захват:
        если два процесса (например, два одновременных запуска скрипта)
        оба вызовут get_pending() и получат один и тот же элемент, только
        один из вызовов mark_processing() реально изменит строку (affected
        rows = 1); второй увидит status уже НЕ 'pending' и получит affected
        rows = 0 → None. Раньше это был безусловный UPDATE ... WHERE id = %s —
        оба процесса "успешно" помечали один и тот же элемент и оба
        генерировали постер повторно.

        Заодно проставляет processing_started_at — момент реального начала
        обработки, а не момент постановки в очередь (created_at) — и
        увеличивает claim_token ("fencing token", см. комментарий у
        _ADD_CLAIM_TOKEN_SQL). Вызывающий код обязан передать возвращённый
        token в последующие mark_done()/mark_failed() — иначе результат
        УЖЕ неактуального захвата (например, воркер, застрявший дольше
        processing_timeout_minutes и перезахваченный заново) может
        перезаписать статус нового, ещё выполняющегося захвата.

        Возвращает claim_token (int), если элемент реально захвачен,
        None — если его уже забрал кто-то другой (нужно пропустить).
        """
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE movie_generation_queue "
                "SET status = 'processing', processing_started_at = NOW(), "
                "    claim_token = claim_token + 1 "
                "WHERE id = %s AND status = 'pending'",
                (queue_id,),
            )
            if cursor.rowcount == 0:
                conn.commit()
                logger.warning(
                    f"Элемент очереди id={queue_id} уже забран другим процессом — пропускаем"
                )
                return None

            cursor.execute(
                "SELECT claim_token FROM movie_generation_queue WHERE id = %s",
                (queue_id,),
            )
            row = cursor.fetchone()
            conn.commit()
            token = row[0] if row else None
            logger.debug(
                f"Элемент очереди id={queue_id} → processing (захвачен, claim_token={token})"
            )
            return token
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"Queue: failed to claim item {queue_id} for processing.",
                details=str(exc),
            ) from exc
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()

    def mark_done(self, queue_id: int, claim_token: int | None = None) -> None:
        """
        Помечает элемент очереди как успешно завершённый.

        claim_token: значение, полученное от mark_processing() при захвате
        этого элемента. Если передано — обновление применяется, только
        если claim_token в БД всё ещё совпадает (fencing token, см.
        mark_processing()); устаревший результат молча игнорируется
        (с предупреждением в лог), а не перезаписывает статус нового
        захвата. Если не передано — обновление безусловное (для элементов,
        которые никогда не проходили через mark_processing(), например
        film_id отсутствует в Sakila — см. вызовы в generate_movie_posters.py).
        """
        self._update_status(queue_id, 'done', claim_token)

    def mark_failed(self, queue_id: int, claim_token: int | None = None) -> None:
        """
        Помечает элемент очереди как неудачный и увеличивает счётчик tries.
        claim_token — см. docstring mark_done().
        """
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            if claim_token is None:
                cursor.execute(
                    "UPDATE movie_generation_queue "
                    "SET status = 'failed', tries = tries + 1 "
                    "WHERE id = %s",
                    (queue_id,),
                )
            else:
                cursor.execute(
                    "UPDATE movie_generation_queue "
                    "SET status = 'failed', tries = tries + 1 "
                    "WHERE id = %s AND claim_token = %s",
                    (queue_id, claim_token),
                )
            conn.commit()
            if cursor.rowcount:
                logger.warning(f"Элемент очереди id={queue_id} помечен как failed.")
            elif claim_token is not None:
                logger.warning(
                    f"Элемент очереди id={queue_id}: устаревший claim_token={claim_token} — "
                    f"переход в failed проигнорирован (элемент уже перезахвачен заново)."
                )
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"Queue: failed to mark item {queue_id} as failed.",
                details=str(exc),
            ) from exc
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()

    # ── Чтение ──────────────────────────────────────────────────────────

    def get_pending(self, limit: int = 10) -> list[dict]:
        """
        Возвращает до `limit` элементов очереди в статусе pending.

        Сортировка по priority DESC (чем выше число — тем раньше обрабатывается),
        затем по film_id ASC (предсказуемый, повторяемый порядок в рамках
        одного приоритета).
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
        Возвращает количество элементов, сгруппированных по статусу.
        Пример: {'pending': 5, 'done': 100, 'failed': 2}
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
        Синхронизирует очередь с завершёнными постерами OpenAI (источник истины).

        Правила по статусам для фильмов БЕЗ завершённого постера OpenAI:
          'done'       → 'pending'   (был завершён MockProvider; нужна настоящая генерация)
          'pending'    → без изменений (уже ждёт; не трогаем)
          'failed'     → без изменений (явная ошибка; используйте --retry-failed для повтора)
          'processing' → 'pending' только если age_minutes >= processing_timeout_minutes
                         (зависло после падения запуска); иначе без изменений
          отсутствует  → INSERT 'pending'

        Для фильмов С завершённым постером OpenAI:
          любой статус  → 'done' (или без изменений, если уже 'done')
          отсутствует   → INSERT 'done'

        tries и created_at существующих строк сохраняются.

        Возвращает:
            {
              'inserted':       созданные новые записи очереди,
              'set_to_pending': существующие записи, изменённые на 'pending',
              'set_to_done':    существующие записи, изменённые на 'done',
              'unchanged':      записи, оставленные в текущем статусе,
            }
        """
        if not all_film_ids:
            return {'inserted': 0, 'set_to_pending': 0, 'set_to_done': 0, 'unchanged': 0}

        conn = self._connect()
        cursor = conn.cursor(dictionary=True)
        try:
            # Получаем текущее состояние очереди плюс возраст для определения зависших задач
            # COALESCE(processing_started_at, created_at): для 'processing'-
            # элементов возраст считаем от момента реального захвата
            # (processing_started_at), а не от постановки в очередь —
            # иначе элемент, долго прождавший в pending, немедленно
            # считался бы "зависшим" сразу после начала обработки.
            # created_at остаётся fallback для элементов НЕ в processing
            # (у них processing_started_at всегда NULL) — им конкретное
            # значение age_minutes здесь не важно, оно используется только
            # в ветке status == 'processing' ниже.
            placeholders = ', '.join(['%s'] * len(all_film_ids))
            cursor.execute(
                f"SELECT film_id, status, "
                f"TIMESTAMPDIFF(MINUTE, COALESCE(processing_started_at, created_at), NOW()) "
                f"AS age_minutes "
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
                    # У фильма есть завершённый постер OpenAI → должен быть 'done'
                    if row is None:
                        to_insert_done.append(fid)
                    elif row['status'] == 'done':
                        unchanged += 1
                    else:
                        to_set_done.append(fid)
                else:
                    # Нет завершённого постера OpenAI — правила по статусам
                    if row is None:
                        to_insert_pending.append(fid)
                    elif row['status'] == 'done':
                        to_set_pending.append(fid)       # был mock-done; ставим в очередь заново
                    elif row['status'] == 'pending':
                        unchanged += 1
                    elif row['status'] == 'failed':
                        unchanged += 1                   # оставляем; используйте --retry-failed
                    elif row['status'] == 'processing':
                        age = row.get('age_minutes') or 0
                        if age >= processing_timeout_minutes:
                            to_set_pending.append(fid)   # зависший запуск; сбрасываем
                        else:
                            unchanged += 1               # ещё активен; оставляем

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
                "Синхронизация очереди: inserted=%d set_pending=%d set_done=%d unchanged=%d",
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
        Сбрасывает элементы очереди со статусом failed обратно в 'pending'
        для явного повтора.

        Если указан film_id: сбрасывается только этот фильм.
        Иначе: сбрасываются все неудачные элементы.
        Возвращает количество изменённых элементов.
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
            logger.info("retry_failed: сброшено в pending %d элемент(ов) (film_id=%s)", count, film_id)
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
        """Возвращает количество элементов очереди с заданным статусом."""
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

    # ── Приватный вспомогательный метод ────────────────────────────────────

    def _update_status(
        self, queue_id: int, status: str, claim_token: int | None = None
    ) -> None:
        conn = self._connect()
        cursor = None
        try:
            cursor = conn.cursor()
            if claim_token is None:
                cursor.execute(
                    "UPDATE movie_generation_queue SET status = %s WHERE id = %s",
                    (status, queue_id),
                )
            else:
                cursor.execute(
                    "UPDATE movie_generation_queue SET status = %s "
                    "WHERE id = %s AND claim_token = %s",
                    (status, queue_id, claim_token),
                )
            conn.commit()
            if cursor.rowcount:
                logger.debug(f"Элемент очереди id={queue_id} → {status}")
            elif claim_token is not None:
                logger.warning(
                    f"Элемент очереди id={queue_id}: устаревший claim_token={claim_token} — "
                    f"переход в {status} проигнорирован (элемент уже перезахвачен заново)."
                )
        except mysql.connector.Error as exc:
            raise RepositoryError(
                f"Queue: failed to set status={status} for id={queue_id}.",
                details=str(exc),
            ) from exc
        finally:
            if cursor is not None:
                cursor.close()
            conn.close()
