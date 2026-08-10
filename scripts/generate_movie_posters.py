"""
scripts/generate_movie_posters.py
──────────────────────────────────────────────────────────────────────
Batch poster generator for ITCH Films using OpenAI gpt-image-2.

Usage (run from project root):
    python scripts/generate_movie_posters.py [options]

Options:
    --limit N       Max posters to generate in this run (default: 5).
    --film-id ID    Generate a poster for one specific film only.
    --dry-run       Show what would be generated; no API calls, no DB writes.

Examples:
    # See the next 5 films that would be generated (safe preview)
    python scripts/generate_movie_posters.py --dry-run

    # Generate one poster for film_id=1
    python scripts/generate_movie_posters.py --film-id 1

    # Generate up to 5 posters (default)
    python scripts/generate_movie_posters.py

    # Continue the queue, up to 20 posters
    python scripts/generate_movie_posters.py --limit 20

Safety rules:
    - Never prints the OpenAI API key.
    - Skips films that already have a completed poster from OpenAI.
    - Mock posters (provider='mock') are NOT counted as final — those films
      will be regenerated with OpenAI when their queue item is pending.
    - Does NOT auto-retry failed items in the same run.
    - Does NOT start mass generation automatically.

New flags (budget-safe mass generation):
    --target-from-db              Auto-calculate remaining from Sakila vs movie_posters.
    --max-api-attempts N          Hard cap on actual OpenAI API calls (overrides limit).
    --estimated-budget X.XX       Abort before starting if estimated cost > X.XX USD.
    --cost-per-image X.XXX        Output image cost per call (default: 0.005 USD —
                                  official price for gpt-image-2 quality=low 1024x1536).
"""


import os
import sys
import time
import argparse
import logging

# Force UTF-8 output on Windows (default console is cp1252)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Path setup ────────────────────────────────────────────────────────
_script_dir   = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_itch_films   = os.path.join(_project_root, 'itch_films')

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _itch_films not in sys.path:
    sys.path.insert(0, _itch_films)

from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, '.env'))

# ── Imports ───────────────────────────────────────────────────────────
import mysql.connector
import local_settings

from services.ai_posters import (
    PosterStorage,
    PosterRepository,
    GenerationQueue,
    PosterService,
    build_prompt,
)
from services.ai_posters.providers.openai_provider import OpenAIProvider, DEFAULT_MODEL
from services.ai_posters.exceptions import ProviderConfigurationError

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────
STORAGE_DIR           = os.path.join(_project_root, 'storage', 'posters')
BATCH_SIZE            = 50
LINE                  = '=' * 52
DEFAULT_COST_PER_IMG  = 0.005   # USD — official price: gpt-image-2, quality=low, 1024x1536
BUDGET_HARD_LIMIT     = 7.50    # USD — never spend more than this in one run


# ── Argument parsing ──────────────────────────────────────────────────

def _positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid integer")
    if n <= 0:
        raise argparse.ArgumentTypeError(
            f"must be a positive integer greater than 0 (got {n})"
        )
    return n


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments. Returns a Namespace with limit, film_id, dry_run."""
    parser = argparse.ArgumentParser(
        description='ITCH Films — AI Poster Generator (OpenAI gpt-image-2)',
    )
    parser.add_argument(
        '--limit',
        type=_positive_int,
        default=5,
        metavar='N',
        help='Maximum number of posters to generate in this run (default: 5, must be > 0).',
    )
    parser.add_argument(
        '--film-id',
        type=_positive_int,
        default=None,
        dest='film_id',
        metavar='ID',
        help='Generate a poster for this specific film_id only (must be > 0).',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        dest='dry_run',
        help='Show what would be generated without calling the OpenAI API.',
    )
    parser.add_argument(
        '--sync-queue',
        action='store_true',
        dest='sync_queue',
        help=(
            'Synchronise movie_generation_queue with completed OpenAI posters, '
            'then exit. No API calls. No file writes. No movie_posters changes.'
        ),
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        dest='retry_failed',
        help=(
            'Reset failed queue items to pending, then exit. '
            'Combine with --film-id to retry a single film. '
            'No API calls. No file writes. No movie_posters changes.'
        ),
    )
    parser.add_argument(
        '--target-from-db',
        action='store_true',
        dest='target_from_db',
        help=(
            'Dynamically calculate remaining films from Sakila vs completed OpenAI posters. '
            'Overrides --limit. Stops when every Sakila film has a valid OpenAI poster.'
        ),
    )
    parser.add_argument(
        '--max-api-attempts',
        type=_positive_int,
        default=None,
        dest='max_api_attempts',
        metavar='N',
        help=(
            'Hard cap on actual OpenAI API calls in this run. '
            'Overrides --limit and --target-from-db limit. Safety circuit-breaker.'
        ),
    )
    parser.add_argument(
        '--estimated-budget',
        type=float,
        default=None,
        dest='estimated_budget',
        metavar='USD',
        help=(
            'Abort before generation if estimated cost exceeds this amount (USD). '
            'Example: --estimated-budget 8.00'
        ),
    )
    parser.add_argument(
        '--cost-per-image',
        type=float,
        default=DEFAULT_COST_PER_IMG,
        dest='cost_per_image',
        metavar='USD',
        help=(
            f'Output image cost per API call in USD '
            f'(default: {DEFAULT_COST_PER_IMG} — official price for '
            f'gpt-image-2 quality=low 1024x1536). '
            f'Does not include input token cost.'
        ),
    )
    return parser.parse_args()


# ── Database helpers ──────────────────────────────────────────────────

def _fetch_films() -> list[dict]:

    conn   = mysql.connector.connect(**local_settings.dbconfig)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT   f.film_id,
                 f.title,
                 f.description,
                 MIN(c.name) AS genre
        FROM     film f
        LEFT JOIN film_category fc ON f.film_id      = fc.film_id
        LEFT JOIN category      c  ON fc.category_id = c.category_id
        GROUP BY f.film_id, f.title, f.description
        ORDER BY f.film_id
    """)
    films = cursor.fetchall()
    cursor.close()
    conn.close()
    return films


def _fetch_film_by_id(film_id: int) -> dict | None:
    """
    Fetch a single film from Sakila by film_id.

    Returns a dict with film_id, title, description, genre, release_year,
    rating — or None if the film does not exist.
    Prompt is always built from title + genre + description, never from ID alone.
    """
    conn   = mysql.connector.connect(**local_settings.dbconfig)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT   f.film_id,
                 f.title,
                 f.description,
                 f.release_year,
                 f.rating,
                 MIN(c.name) AS genre
        FROM     film f
        LEFT JOIN film_category fc ON f.film_id      = fc.film_id
        LEFT JOIN category      c  ON fc.category_id = c.category_id
        WHERE    f.film_id = %s
        GROUP BY f.film_id, f.title, f.description, f.release_year, f.rating
    """, (film_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def _reset_stuck_processing(queue: GenerationQueue) -> int:
    """
    Reset queue items stuck in 'processing' back to 'pending'.
    These are leftovers from a run that was interrupted mid-generation.
    """
    conn   = mysql.connector.connect(**local_settings.dbconfig_write)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE movie_generation_queue "
        "SET status = 'pending' WHERE status = 'processing'"
    )
    count = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return count


# ── Prompt helpers ────────────────────────────────────────────────────

def _build_description(film: dict) -> tuple[str, bool]:
    """
    Return (effective_description, is_fallback).

    If description is empty or None, falls back to a sentence built from
    title + genre (never invents content). is_fallback=True signals the
    caller to log a warning before generating.

    The prompt is never built from film_id alone.
    """
    desc = (film.get('description') or '').strip()
    if desc:
        return desc, False
    genre    = (film.get('genre') or 'Drama').strip()
    fallback = f"{film['title']}. A {genre} film."
    return fallback, True


# ── Output helpers ────────────────────────────────────────────────────

def _print_film_preview(
    film: dict,
    prompt: str,
    negative_prompt: str,
    is_fallback: bool = False,
) -> None:
    """Print a safe preview of what will be sent to OpenAI. Never prints the key."""
    raw_desc = film.get('description') or ''
    if is_fallback:
        desc_line = '[FALLBACK — description is empty in DB, using title + genre]'
    else:
        desc_line = raw_desc[:150] + ('...' if len(raw_desc) > 150 else '')

    print()
    print("  ── Film preview ──────────────────────────────────")
    print(f"  film_id      : {film['film_id']}")
    print(f"  title        : {film['title']}")
    print(f"  genre        : {film.get('genre') or 'N/A'}")
    print(f"  release_year : {film.get('release_year') or 'N/A'}")
    print(f"  rating       : {film.get('rating') or 'N/A'}")
    print(f"  description  : {desc_line}")
    print(f"  style        : auto")
    print(f"  prompt len   : {len(prompt)} chars")


def _print_banner(args: argparse.Namespace, model: str) -> None:
    mode = 'DRY-RUN (no API calls)' if args.dry_run else 'LIVE'
    print(LINE)
    print("  ITCH Films — AI Poster Generator")
    print(f"  Provider : OpenAI  ({model})")
    print(f"  Storage  : {STORAGE_DIR}")
    print(f"  Mode     : {mode}")
    if args.film_id is not None:
        print(f"  Film ID  : {args.film_id}")
    else:
        print(f"  Limit    : {args.limit} posters per run")
    print(LINE)


def _print_summary(generated: int, skipped: int, failed: int, total: int) -> None:
    print()
    print(LINE)
    print(f"  Generated : {generated}")
    print(f"  Skipped   : {skipped}  (OpenAI poster already exists)")
    print(f"  Failed    : {failed}")
    print(f"  Total     : {total}")
    print(LINE)


# ── Single-film mode ──────────────────────────────────────────────────

def _run_single_film(
    args: argparse.Namespace,
    service,           # PosterService | None  (None when dry_run=True)
    repository: PosterRepository,
) -> None:
    """
    Generate a poster for exactly one film, identified by --film-id.

    Loads title, genre, description, release_year, rating from Sakila.
    Exits with code 1 if the film is not found.
    Falls back to title+genre if description is empty — does NOT invent content.
    """
    film = _fetch_film_by_id(args.film_id)
    if film is None:
        print(f"\n[ERROR] Film ID {args.film_id} was not found in Sakila.")
        sys.exit(1)

    desc, is_fallback = _build_description(film)
    if is_fallback:
        print(
            f"\n  [FALLBACK] Film {args.film_id} has no description in DB. "
            f"Using title + genre instead."
        )

    prompt, negative_prompt = build_prompt(
        title=film['title'],
        genre=film.get('genre') or '',
        description=desc,
        style='auto',
    )

    _print_film_preview(film, prompt, negative_prompt, is_fallback)

    if args.dry_run:
        print(f"\n  [DRY-RUN] No API call made. Prompt is {len(prompt)} chars.")
        return

    if repository.openai_poster_exists(film['film_id']):
        print(f"\n  [SKIP] Film {args.film_id} already has a completed OpenAI poster.")
        return

    print(f"\n  Generating poster for: {film['title']}")
    print("  (this may take 20-30 seconds)")
    try:
        poster_id = service.generate(
            film_id=film['film_id'],
            title=film['title'],
            genre=film.get('genre') or '',
            description=desc,
        )
        url = service.get_poster_url(film['film_id'])
        print(f"\n  [OK] poster_id={poster_id}  url={url}")
    except Exception as exc:
        print(f"\n  [ERROR] {exc}")
        sys.exit(1)


# ── Retry failed items ────────────────────────────────────────────────

def _run_retry_failed(args: argparse.Namespace, queue: GenerationQueue) -> None:
    """
    Explicitly reset failed queue items back to 'pending'.

    With --film-id N : resets only that film.
    Without --film-id : shows the count of failed items, then resets all.

    Does NOT call OpenAI. Does NOT create files. Does NOT write to movie_posters.
    """
    print(LINE)
    print("  ITCH Films — Retry Failed Queue Items")
    print(LINE)

    if args.film_id is not None:
        count = queue.retry_failed(film_id=args.film_id)
        if count:
            print(f"\n  [OK] film_id={args.film_id} reset: 'failed' → 'pending'.")
        else:
            print(
                f"\n  [SKIP] film_id={args.film_id} was not in 'failed' status "
                f"(already pending / done / processing)."
            )
    else:
        total_failed = queue.count_by_status('failed')
        print(f"\n  Failed items in queue: {total_failed}")
        if total_failed == 0:
            print("  Nothing to reset.")
        else:
            count = queue.retry_failed()
            print(f"  [OK] Reset {count} item(s): 'failed' → 'pending'.")

    print()
    print(LINE)
    print("  No OpenAI API calls made.")
    print("  No files created.")
    print("  movie_posters table was NOT modified.")


# ── Queue synchronisation ─────────────────────────────────────────────

def _run_sync_queue(
    repository: PosterRepository,
    queue: GenerationQueue,
) -> None:
    """
    Synchronise movie_generation_queue with completed OpenAI poster status.

    Source of truth: movie_posters WHERE provider='openai' AND status='completed'.
    Films with completed OpenAI poster  → queue status 'done'.
    All other films                     → queue status 'pending'.
    Films not in queue                  → INSERT as 'pending'.

    Does NOT call OpenAI API. Does NOT write to movie_posters. Does NOT create files.
    """
    print(LINE)
    print("  ITCH Films — Queue Sync (OpenAI source of truth)")
    print(LINE)

    print("\n[1/3] Fetching films from Sakila (read-only)...")
    films = _fetch_films()
    all_film_ids = [f['film_id'] for f in films]
    print(f"      Found {len(all_film_ids)} films.")

    print("\n[2/3] Fetching completed OpenAI poster IDs (read-only)...")
    openai_done_ids = repository.get_openai_completed_film_ids()
    print(f"      Completed OpenAI posters : {len(openai_done_ids)}")
    print(f"      Films needing generation : {len(all_film_ids) - len(openai_done_ids)}")

    print("\n[3/3] Synchronising queue...")
    result = queue.sync_for_openai_generation(all_film_ids, openai_done_ids)

    print()
    print(LINE)
    print("  Sync complete:")
    print(f"  Inserted (new entries) : {result['inserted']}")
    print(f"  Set to pending         : {result['set_to_pending']}")
    print(f"  Set to done            : {result['set_to_done']}")
    print(f"  Unchanged              : {result['unchanged']}")
    print(LINE)
    print()
    print("  No OpenAI API calls made.")
    print("  No files created.")
    print("  movie_posters table was NOT modified.")


# ── Batch dry-run (read-only) ─────────────────────────────────────────

def _run_batch_dry(args: argparse.Namespace, repository: PosterRepository) -> None:
    """
    Read-only dry-run preview for batch mode.

    Performs only SELECT queries — never creates tables, writes to the queue,
    calls the OpenAI API, or creates files. The generation queue is not
    consulted at all; candidate films come directly from Sakila.
    """
    print("\n[DRY-RUN] Fetching films from Sakila (read-only)...")
    films = _fetch_films()
    print(f"          Found {len(films)} films in Sakila.")

    openai_done_ids = repository.get_openai_completed_film_ids()
    candidates = [f for f in films if f['film_id'] not in openai_done_ids]

    # Resolve effective limit for dry-run
    if getattr(args, 'target_from_db', False):
        dry_limit = len(candidates)
    else:
        dry_limit = args.limit
    if getattr(args, 'max_api_attempts', None) is not None:
        dry_limit = min(dry_limit, args.max_api_attempts)

    selected = candidates[:min(dry_limit, 10)]   # show at most 10 in dry-run

    print(f"          Films with completed OpenAI poster : {len(openai_done_ids)}")
    print(f"          Films without OpenAI poster        : {len(candidates)}")
    print(f"          Would generate up to               : {dry_limit}")
    print(f"          Showing preview for                : {len(selected)}")

    for film in selected:
        desc, is_fallback = _build_description(film)
        prompt, negative_prompt = build_prompt(
            title=film['title'],
            genre=film.get('genre') or '',
            description=desc,
            style='auto',
        )
        _print_film_preview(film, prompt, negative_prompt, is_fallback)

    print()
    print("  [DRY-RUN] No tables created. No queue modified.")
    print("  [DRY-RUN] No OpenAI API calls. No files written.")


# ── Batch mode (live) ─────────────────────────────────────────────────

def _run_batch(
    args: argparse.Namespace,
    service,           # PosterService | None  (None when dry_run=True)
    repository: PosterRepository,
    queue: GenerationQueue,
) -> None:
    """
    Process the generation queue up to --limit actual generations.

    In dry-run mode delegates immediately to _run_batch_dry() which is
    fully read-only. All queue and table operations are skipped.

    Skip logic (live mode): a film is skipped only if it has a completed
    poster with provider='openai'. Skips do NOT count toward --limit.
    Mock posters (provider='mock') do NOT prevent regeneration.
    """
    if args.dry_run:
        _run_batch_dry(args, repository)
        return

    # ── Step 1: tables ────────────────────────────────────────────────
    print("\n[1/4] Creating tables...")
    repository.create_table()
    queue.create_table()
    print("      Done.")


    # ── Step 2: fetch films ───────────────────────────────────────────
    print("\n[2/4] Fetching films from Sakila...")
    films = _fetch_films()
    all_film_ids = [f['film_id'] for f in films]
    film_lookup: dict[int, dict] = {f['film_id']: f for f in films}
    print(f"      Found {len(films)} films.")

    # ── Step 3: sync queue (source of truth: completed OpenAI posters) ─
    # Replaces bulk_enqueue + reset_stuck_processing.
    # Films with OpenAI poster → done; all others → pending (even if done-from-mock).
    print("\n[3/4] Synchronising queue with OpenAI poster status...")
    openai_done_ids = repository.get_openai_completed_film_ids()
    sync_result     = queue.sync_for_openai_generation(all_film_ids, openai_done_ids)
    print(f"      Inserted        : {sync_result['inserted']}")
    print(f"      Set to pending  : {sync_result['set_to_pending']}")
    print(f"      Set to done     : {sync_result['set_to_done']}")
    print(f"      Unchanged       : {sync_result['unchanged']}")

    # ── Resolve effective limit (--target-from-db / --max-api-attempts) ──
    remaining_films = len(all_film_ids) - len(openai_done_ids)

    if getattr(args, 'target_from_db', False):
        effective_limit = remaining_films
        print(f"\n      [target-from-db] Remaining films: {remaining_films}")
    else:
        effective_limit = args.limit

    if getattr(args, 'max_api_attempts', None) is not None:
        effective_limit = min(effective_limit, args.max_api_attempts)
        print(f"      [max-api-attempts] Hard cap applied: {args.max_api_attempts}")

    # ── Budget pre-check ──────────────────────────────────────────────
    cost_per_img   = getattr(args, 'cost_per_image', DEFAULT_COST_PER_IMG)
    budget_limit   = getattr(args, 'estimated_budget', None)
    retry_reserve  = min(int(effective_limit * 0.10), 100)
    max_attempts   = effective_limit + retry_reserve
    estimated_cost = max_attempts * cost_per_img

    print(f"\n      Budget estimate:")
    print(f"        cost_per_image     = ${cost_per_img:.4f}")
    print(f"        effective_limit    = {effective_limit}")
    print(f"        retry_reserve      = {retry_reserve}")
    print(f"        max_api_attempts   = {max_attempts}")
    print(f"        estimated_max_cost = ${estimated_cost:.2f}")
    if budget_limit is not None:
        print(f"        budget_limit       = ${budget_limit:.2f}")
        if estimated_cost > budget_limit:
            print(
                f"\n[BUDGET ABORT] Estimated cost ${estimated_cost:.2f} "
                f"exceeds budget ${budget_limit:.2f}.\n"
                f"  Use --max-api-attempts to cap at a safe number.\n"
                f"  Safe cap: --max-api-attempts {int(budget_limit / cost_per_img)}"
            )
            sys.exit(1)
    elif estimated_cost > BUDGET_HARD_LIMIT:
        print(
            f"\n[BUDGET WARNING] Estimated ${estimated_cost:.2f} "
            f"exceeds hard limit ${BUDGET_HARD_LIMIT:.2f}.\n"
            f"  Use --estimated-budget to explicitly allow, "
            f"or --max-api-attempts to cap.\n"
            f"  Safe cap: --max-api-attempts {int(BUDGET_HARD_LIMIT / cost_per_img)}"
        )
        sys.exit(1)

    # ── Step 4: process queue — stop when api_attempts reaches hard cap ──
    api_cap = effective_limit   # max actual OpenAI API calls
    print(f"\n[4/4] Generating posters (api_cap={api_cap})...")
    generated   = 0    # successful generations
    skipped     = 0    # films that already had an OpenAI poster
    failed      = 0    # generation failures
    api_attempts = 0   # actual calls sent to OpenAI Images API (success + failure)

    while api_attempts < api_cap:
        pending = queue.get_pending(limit=BATCH_SIZE)
        if not pending:
            break

        for item in pending:
            if api_attempts >= api_cap:
                break

            queue_id = item['id']
            film_id  = item['film_id']
            film     = film_lookup.get(film_id)

            if not film:
                # No API call — just fail the queue item and move on
                queue.mark_failed(queue_id)
                failed += 1
                print(f"  [MISSING ] [{film_id:>4}] film not found in Sakila")
                continue

            # Skip if an OpenAI poster already exists — mock posters don't count
            if repository.openai_poster_exists(film_id):
                queue.mark_done(queue_id)
                skipped += 1
                continue   # skips do NOT count as api_attempts

            desc, is_fallback = _build_description(film)

            queue.mark_processing(queue_id)
            start = time.monotonic()
            api_attempts += 1   # increment here — counts this actual OpenAI API call
            try:
                poster_id = service.generate(
                    film_id=film_id,
                    title=film['title'],
                    genre=film.get('genre') or '',
                    description=desc,
                )
                elapsed = round(time.monotonic() - start, 1)
                queue.mark_done(queue_id)
                generated += 1
                url  = service.get_poster_url(film_id)
                note = ' [fallback-desc]' if is_fallback else ''
                print(
                    f"  [GENERATED] [{film_id:>4}] "
                    f"{film['title'][:40]:<40}  {url}  ({elapsed}s){note}"
                )

                # Progress report every 50 successful generations
                if generated % 50 == 0:
                    valid_now  = len(openai_done_ids) + generated
                    left_now   = len(all_film_ids) - valid_now
                    api_cost   = round(api_attempts * cost_per_img, 4)
                    print()
                    print(f"  ── Progress ────────────────────────────────────")
                    print(f"  Sakila films          : {len(all_film_ids)}")
                    print(f"  Valid posters before  : {len(openai_done_ids)}")
                    print(f"  Generated this run    : {generated}")
                    print(f"  Current valid total   : {valid_now}")
                    print(f"  Remaining             : {left_now}")
                    print(f"  API attempts          : {api_attempts}")
                    print(f"  Failed attempts       : {failed}")
                    print(f"  Estimated cost        : ~${api_cost:.4f}")
                    print(f"  ────────────────────────────────────────────────")
                    print()

            except Exception as exc:
                queue.mark_failed(queue_id)
                failed += 1
                print(
                    f"  [FAILED   ] [{film_id:>4}] "
                    f"{film['title'][:40]:<40}  {exc}"
                )

    # ── Final queue stats ─────────────────────────────────────────────
    print("\n[Final] Queue status:")
    for status, count in sorted(queue.get_stats().items()):
        print(f"        {status:<12}: {count}")

    actual_cost = round(api_attempts * cost_per_img, 4)
    print(f"\n[Final] API attempts this run : {api_attempts}")
    print(f"[Final] Estimated output cost : ~${actual_cost:.4f}")

    _print_summary(generated, skipped, failed, len(films))


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # --sync-queue, --retry-failed, and --dry-run do not call the API.
    # Provider is created only for live generation (batch or single-film).
    provider = None
    model    = os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_MODEL)
    needs_provider = not args.dry_run and not args.sync_queue and not args.retry_failed
    if needs_provider:
        try:
            provider = OpenAIProvider()
            model    = provider.model_name()
        except ProviderConfigurationError as exc:
            print(f"\n[CONFIG ERROR] {exc}")
            print("  Add OPENAI_API_KEY to your .env file.")
            sys.exit(1)

    storage    = PosterStorage(STORAGE_DIR)
    repository = PosterRepository()
    queue      = GenerationQueue()
    service    = (
        PosterService(provider=provider, storage=storage, repository=repository)
        if provider else None
    )

    # Maintenance commands: exit before banner and generation
    if args.sync_queue:
        _run_sync_queue(repository, queue)
        return

    if args.retry_failed:
        _run_retry_failed(args, queue)
        return

    _print_banner(args, model)

    if args.film_id is not None:
        _run_single_film(args, service, repository)
    else:
        _run_batch(args, service, repository, queue)


if __name__ == '__main__':
    main()
