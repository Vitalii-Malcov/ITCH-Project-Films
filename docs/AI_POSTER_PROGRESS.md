# AI Poster Generation — Progress Checkpoint

> **⚠️ АРХИВНЫЙ ДОКУМЕНТ.** Это снимок состояния на 2026-07-10, ДО массовой генерации
> постеров. Все цифры ниже (queue state, "Completed: 5", "Failed: film_id=10") устарели
> и оставлены только как исторический контекст хода разработки.
>
> **Актуальный статус проекта (2026-08-10):** 1001 фильм · 996 постеров через OpenAI ·
> 5 через MockProvider fallback (moderation_blocked) · очередь done=996/failed=5/pending=0 ·
> 1001/1001 фильмов имеют отображаемый постер · 162 pytest теста passed.
> Подробности: [`docs/SESSION_SUMMARY_2026-07-11.md`](SESSION_SUMMARY_2026-07-11.md) и
> раздел «AI-постеры — архитектура и текущее состояние» в
> [`PROJECT_ARCHITECTURE.md`](../PROJECT_ARCHITECTURE.md).

**Date:** 2026-07-10
**Branch:** `ai-poster-service`
**Last commit before this checkpoint:** `3e41a08 Add OpenAI poster provider and batch generation controls`

---

## Model and Parameters

| Parameter    | Value          |
|--------------|----------------|
| Provider     | OpenAI         |
| Model        | `gpt-image-2`  |
| Quality      | `low`          |
| Size         | `1024x1536`    |
| Output format| WebP           |
| Compression  | 80             |

Model is read from `OPENAI_IMAGE_MODEL` env var (fallback: `gpt-image-2`).

---

## What Is Implemented

### Core Services (`services/ai_posters/`)

| File | Purpose |
|---|---|
| `providers/openai_provider.py` | OpenAIProvider — calls Images API, returns raw WebP bytes |
| `providers/mock.py` | MockProvider — returns a solid-color WebP placeholder, no API, for local dev |
| `prompt_builder.py` | Builds prompt from film title + genre + description |
| `poster_service.py` | Orchestrates prompt → generate → storage → DB save |
| `poster_repository.py` | CRUD for `movie_posters` table; `get_openai_completed_film_ids()` |
| `poster_storage.py` | Saves WebP to `storage/posters/`, auto-numbered filenames |
| `queue.py` | `GenerationQueue` — full queue lifecycle with safe sync |
| `exceptions.py` | Custom exception hierarchy |

### Script (`scripts/generate_movie_posters.py`)

CLI entry point with argparse flags:

| Flag | Purpose |
|---|---|
| `--limit N` | Generate up to N posters (default: 5) |
| `--film-id ID` | Generate a single specific film |
| `--dry-run` | Read-only preview — no API, no DB, no files |
| `--sync-queue` | Sync queue with OpenAI poster DB as source of truth |
| `--retry-failed` | Reset `failed` items to `pending` for retry |

All flags validated with `_positive_int()` — rejects 0 and negatives at parse time.

### Key Design Decisions

- **`sync_for_openai_generation()` rules** — `failed` stays `failed` (not auto-reset);
  `processing` items older than 30 min are reset (stuck detection);
  `done` items without OpenAI poster are reset to `pending` (mock → OpenAI migration)
- **`ORDER BY priority DESC, film_id ASC`** — predictable, repeatable generation order
- **`--retry-failed`** is the only way to re-queue `failed` items
- **`--dry-run`** is structurally isolated — never receives provider, queue write methods, or service
- **Two DB connections** — Sakila (read) for film metadata, write DB for posters + queue

---

## Last pytest Results (2026-07-10)

```
162 passed in 3.46s
```

Test classes:
- `TestParseArgs` — 7 tests
- `TestBuildDescription` — 7 tests
- `TestOpenaiPosterExists` — 5 tests
- `TestGetOpenaiCompletedFilmIds` — 4 tests
- `TestRunSingleFilm` — 8 tests
- `TestRunBatch` — 10 tests
- `TestDryRunSafety` — 13 tests
- `TestQueueSync` — 29 tests (includes retry-failed, ordering, film_id=10 stays failed)

---

## Current Queue State (2026-07-10) — ⚠️ HISTORICAL, до массовой генерации

| Status     | Count |
|------------|-------|
| `done`     | 5     |
| `pending`  | 995   |
| `failed`   | 1     |
| `processing` | 0  |

> Финальное состояние очереди (2026-08-10): `done=996`, `failed=5`, `pending=0`,
> `processing=0`. См. banner в начале документа.

### First 10 Pending film_ids (priority DESC, film_id ASC)

`4, 5, 6, 7, 8, 9, 13, 14, 15, 16`

---

## Completed OpenAI Posters — ⚠️ HISTORICAL, до массовой генерации

**Count: 5** (на момент чекпоинта 2026-07-10; финально — 996, см. banner выше)

| film_id | Notes |
|---------|-------|
| 1  | Generated OK |
| 2  | Generated OK |
| 3  | Generated OK |
| 11 | Generated OK |
| 12 | Generated OK |

---

## Failed Items — ⚠️ HISTORICAL, film_id=10 больше не failed

| film_id | Title            | tries | Reason              |
|---------|-----------------|-------|---------------------|
| 10      | ALADDIN CALENDAR | 1     | `moderation_blocked` |

**Reason details:** OpenAI output moderation rejected the image at generation stage.
HTTP 400, `code: moderation_blocked`, `stage: output`, `category: other`.
This is an OpenAI content policy decision — not a code bug.

> **Обновление:** film_id=10 (ALADDIN CALENDAR) был успешно сгенерирован через OpenAI
> в ходе последующей массовой генерации — сейчас имеет реальный постер (провайдер
> `openai`, статус `completed`), проверено в галерее. Финальный список из 5 постоянно
> заблокированных фильмов другой: film_id 54, 153, 516, 680, 792
> (BANGER PINOCCHIO, CITIZEN SHREK, LEGEND JEDI, PINOCCHIO SIMON, SHREK LICENSE) —
> вероятно из-за trademark-названий (SHREK/PINOCCHIO/JEDI). Для них используется
> `MockProvider` как постоянный fallback.

---

## Continuation Command — ⚠️ HISTORICAL, уже выполнено

Этот раздел описывал план на "завтра" от 2026-07-10. Массовая генерация была
выполнена в последующих сессиях (см. `SESSION_SUMMARY_2026-07-11.md`), команды ниже
сохранены только для истории и не должны запускаться повторно без явного решения:

```
.venv/Scripts/python.exe scripts/generate_movie_posters.py --limit 5
```

**Safety rules before running (актуально при любой будущей генерации):**
1. Run `--dry-run` first to see candidates.
2. Verify `.env` has `OPENAI_API_KEY` set.
3. Do NOT run `--retry-failed` without explicit decision.
4. Do NOT run `--limit` greater than what was agreed.
5. Do NOT push without review.

---

## Security Checklist

- [x] `.env` is in `.gitignore` — never committed
- [x] API key only read via `os.getenv()`, never printed
- [x] No credentials in source code or logs
- [x] `storage/posters/` is gitignored — no WebP in commits
- [x] `--dry-run` is structurally read-only (no provider, no queue writes)

---

## Files Changed in This Session (uncommitted at checkpoint) — ⚠️ HISTORICAL

Все файлы из этого списка были закоммичены в последующих коммитах на ветке
`ai-poster-service` (см. `git log`). Список сохранён только как исторический контекст.

| File | Changes |
|---|---|
| `scripts/generate_movie_posters.py` | `--retry-failed`, `_run_retry_failed()`, `_run_batch_dry()` isolated, `_positive_int()` validator, dry-run model from env var |
| `services/ai_posters/queue.py` | `sync_for_openai_generation()` rewritten (failed=unchanged, processing age check), `retry_failed()`, `count_by_status()`, `get_pending()` order fixed |
| `tests/test_generate_posters.py` | 162 tests — `TestQueueSync` fully rewritten, 8 new tests added |