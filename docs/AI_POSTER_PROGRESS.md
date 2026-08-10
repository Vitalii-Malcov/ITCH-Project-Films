# AI Poster Generation — Progress Checkpoint

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
| `providers/mock_provider.py` | MockProvider — returns blank PNG, no API, for local dev |
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

## Current Queue State (2026-07-10)

| Status     | Count |
|------------|-------|
| `done`     | 5     |
| `pending`  | 995   |
| `failed`   | 1     |
| `processing` | 0  |

### First 10 Pending film_ids (priority DESC, film_id ASC)

`4, 5, 6, 7, 8, 9, 13, 14, 15, 16`

---

## Completed OpenAI Posters

**Count: 5**

| film_id | Notes |
|---------|-------|
| 1  | Generated OK |
| 2  | Generated OK |
| 3  | Generated OK |
| 11 | Generated OK |
| 12 | Generated OK |

---

## Failed Items

| film_id | Title            | tries | Reason              |
|---------|-----------------|-------|---------------------|
| 10      | ALADDIN CALENDAR | 1     | `moderation_blocked` |

**Reason details:** OpenAI output moderation rejected the image at generation stage.
HTTP 400, `code: moderation_blocked`, `stage: output`, `category: other`.
This is an OpenAI content policy decision — not a code bug.

**Action:** The item stays `failed`. It will NOT be auto-retried on future `--limit` runs.
To retry manually (only when intentionally decided):

```
.venv/Scripts/python.exe scripts/generate_movie_posters.py --retry-failed --film-id 10
```

**Do NOT run this command automatically tomorrow.**

---

## Continuation Command (Tomorrow)

Generate the next batch of 5 posters (starting from film_id 4):

```
.venv/Scripts/python.exe scripts/generate_movie_posters.py --limit 5
```

**Safety rules before running:**
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

## Files Changed in This Session (uncommitted at checkpoint)

| File | Changes |
|---|---|
| `scripts/generate_movie_posters.py` | `--retry-failed`, `_run_retry_failed()`, `_run_batch_dry()` isolated, `_positive_int()` validator, dry-run model from env var |
| `services/ai_posters/queue.py` | `sync_for_openai_generation()` rewritten (failed=unchanged, processing age check), `retry_failed()`, `count_by_status()`, `get_pending()` order fixed |
| `tests/test_generate_posters.py` | 162 tests — `TestQueueSync` fully rewritten, 8 new tests added |