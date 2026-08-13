"""
scripts/generate_movie_posters.py
──────────────────────────────────────────────────────────────────────
Пакетный генератор постеров для ITCH Films на основе OpenAI gpt-image-2.

Использование (запуск из корня проекта):
    python scripts/generate_movie_posters.py [опции]

Опции:
    --limit N       Максимум постеров за этот запуск (по умолчанию: 5).
    --film-id ID    Сгенерировать постер только для одного конкретного фильма.
    --dry-run       Показать, что было бы сгенерировано; без вызовов API, без записи в БД.

Примеры:
    # Посмотреть следующие 5 фильмов, которые будут сгенерированы (безопасный предпросмотр)
    python scripts/generate_movie_posters.py --dry-run

    # Сгенерировать один постер для film_id=1
    python scripts/generate_movie_posters.py --film-id 1

    # Сгенерировать до 5 постеров (по умолчанию)
    python scripts/generate_movie_posters.py

    # Продолжить очередь, до 20 постеров
    python scripts/generate_movie_posters.py --limit 20

Правила безопасности:
    - Никогда не печатает API-ключ OpenAI.
    - Пропускает фильмы, у которых уже есть завершённый постер от OpenAI.
    - Mock-постеры (provider='mock') НЕ считаются финальными — эти фильмы
      будут перегенерированы через OpenAI, когда их элемент очереди станет pending.
    - НЕ ретраит автоматически неудачные элементы в рамках того же запуска.
    - НЕ запускает массовую генерацию автоматически.

Новые флаги (бюджетно-безопасная массовая генерация):
    --target-from-db              Автоматически вычислить остаток: Sakila минус movie_posters.
    --max-api-attempts N          Жёсткий предел реальных вызовов OpenAI API (переопределяет limit).
    --estimated-budget X.XX       Прервать до начала, если оценочная стоимость > X.XX USD.
    --cost-per-image X.XXX        Стоимость одного изображения за вызов (по умолчанию: 0.005 USD —
                                  официальная цена gpt-image-2 quality=low 1024x1536).
"""


import os
import sys
import time
import argparse
import logging

# Принудительно UTF-8 на Windows (консоль по умолчанию — cp1252)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Настройка путей ────────────────────────────────────────────────────────
_script_dir   = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_itch_films   = os.path.join(_project_root, 'itch_films')

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _itch_films not in sys.path:
    sys.path.insert(0, _itch_films)

from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, '.env'))

# ── Импорты ───────────────────────────────────────────────────────────
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

# ── Логирование ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

# ── Константы ─────────────────────────────────────────────────────────
STORAGE_DIR           = os.path.join(_project_root, 'storage', 'posters')
BATCH_SIZE            = 50
LINE                  = '=' * 52
DEFAULT_COST_PER_IMG  = 0.005   # USD — официальная цена: gpt-image-2, quality=low, 1024x1536
BUDGET_HARD_LIMIT     = 7.50    # USD — никогда не тратить больше за один запуск


# ── Разбор аргументов ──────────────────────────────────────────────────

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
    """Разбирает аргументы CLI. Возвращает Namespace с limit, film_id, dry_run."""
    parser = argparse.ArgumentParser(
        description='ITCH Films — генератор AI-постеров (OpenAI gpt-image-2)',
    )
    parser.add_argument(
        '--limit',
        type=_positive_int,
        default=5,
        metavar='N',
        help='Максимум постеров за этот запуск (по умолчанию: 5, должно быть > 0).',
    )
    parser.add_argument(
        '--film-id',
        type=_positive_int,
        default=None,
        dest='film_id',
        metavar='ID',
        help='Сгенерировать постер только для этого film_id (должно быть > 0).',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        dest='dry_run',
        help='Показать, что было бы сгенерировано, без вызова OpenAI API.',
    )
    parser.add_argument(
        '--sync-queue',
        action='store_true',
        dest='sync_queue',
        help=(
            'Синхронизировать movie_generation_queue с завершёнными постерами OpenAI, '
            'затем выйти. Без вызовов API. Без записи файлов. Без изменений movie_posters.'
        ),
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        dest='retry_failed',
        help=(
            'Сбросить неудачные элементы очереди в pending, затем выйти. '
            'Комбинируйте с --film-id для повтора одного фильма. '
            'Без вызовов API. Без записи файлов. Без изменений movie_posters.'
        ),
    )
    parser.add_argument(
        '--target-from-db',
        action='store_true',
        dest='target_from_db',
        help=(
            'Динамически вычислить оставшиеся фильмы: Sakila минус завершённые постеры OpenAI. '
            'Переопределяет --limit. Останавливается, когда у каждого фильма Sakila есть валидный постер OpenAI.'
        ),
    )
    parser.add_argument(
        '--max-api-attempts',
        type=_positive_int,
        default=None,
        dest='max_api_attempts',
        metavar='N',
        help=(
            'Жёсткий предел реальных вызовов OpenAI API за этот запуск. '
            'Переопределяет --limit и лимит --target-from-db. Защитный предохранитель.'
        ),
    )
    parser.add_argument(
        '--estimated-budget',
        type=float,
        default=None,
        dest='estimated_budget',
        metavar='USD',
        help=(
            'Прервать до начала генерации, если оценочная стоимость превышает эту сумму (USD). '
            'Пример: --estimated-budget 8.00'
        ),
    )
    parser.add_argument(
        '--cost-per-image',
        type=float,
        default=DEFAULT_COST_PER_IMG,
        dest='cost_per_image',
        metavar='USD',
        help=(
            f'Стоимость одного изображения за вызов API в USD '
            f'(по умолчанию: {DEFAULT_COST_PER_IMG} — официальная цена для '
            f'gpt-image-2 quality=low 1024x1536). '
            f'Не включает стоимость входных токенов.'
        ),
    )
    return parser.parse_args()


# ── Вспомогательные функции для БД ──────────────────────────────────────────────────

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
    Получает один фильм из Sakila по film_id.

    Возвращает словарь с film_id, title, description, genre, release_year,
    rating — либо None, если фильм не существует.
    Промпт всегда строится из title + genre + description, никогда только из ID.
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
    Сбрасывает элементы очереди, застрявшие в 'processing', обратно в 'pending'.
    Это остатки от запуска, прерванного посреди генерации.
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


# ── Вспомогательные функции для промпта ────────────────────────────────────────────────

def _build_description(film: dict) -> tuple[str, bool]:
    """
    Возвращает (effective_description, is_fallback).

    Если description пустое или None, откатывается на предложение, построенное
    из title + genre (никогда не выдумывает контент). is_fallback=True сигнализирует
    вызывающему коду вывести предупреждение перед генерацией.

    Промпт никогда не строится только из film_id.
    """
    desc = (film.get('description') or '').strip()
    if desc:
        return desc, False
    genre    = (film.get('genre') or 'Drama').strip()
    fallback = f"{film['title']}. A {genre} film."
    return fallback, True


# ── Вспомогательные функции для вывода ────────────────────────────────────────────────

def _print_film_preview(
    film: dict,
    prompt: str,
    negative_prompt: str,
    is_fallback: bool = False,
) -> None:
    """Печатает безопасный предпросмотр того, что будет отправлено в OpenAI. Никогда не печатает ключ."""
    raw_desc = film.get('description') or ''
    if is_fallback:
        desc_line = '[FALLBACK — description пусто в БД, используем title + genre]'
    else:
        desc_line = raw_desc[:150] + ('...' if len(raw_desc) > 150 else '')

    print()
    print("  ── Предпросмотр фильма ──────────────────────────────────")
    print(f"  film_id      : {film['film_id']}")
    print(f"  title        : {film['title']}")
    print(f"  genre        : {film.get('genre') or 'N/A'}")
    print(f"  release_year : {film.get('release_year') or 'N/A'}")
    print(f"  rating       : {film.get('rating') or 'N/A'}")
    print(f"  description  : {desc_line}")
    print(f"  style        : auto")
    print(f"  длина промпта : {len(prompt)} симв.")


def _print_banner(args: argparse.Namespace, model: str) -> None:
    mode = 'DRY-RUN (без вызовов API)' if args.dry_run else 'БОЕВОЙ'
    print(LINE)
    print("  ITCH Films — генератор AI-постеров")
    print(f"  Провайдер : OpenAI  ({model})")
    print(f"  Хранилище : {STORAGE_DIR}")
    print(f"  Режим     : {mode}")
    if args.film_id is not None:
        print(f"  Film ID   : {args.film_id}")
    else:
        print(f"  Лимит     : {args.limit} постеров за запуск")
    print(LINE)


def _print_summary(generated: int, skipped: int, failed: int, total: int) -> None:
    print()
    print(LINE)
    print(f"  Сгенерировано : {generated}")
    print(f"  Пропущено     : {skipped}  (постер OpenAI уже существует)")
    print(f"  Неудачно      : {failed}")
    print(f"  Всего         : {total}")
    print(LINE)


# ── Режим одного фильма ──────────────────────────────────────────────────

def _run_single_film(
    args: argparse.Namespace,
    service,           # PosterService | None  (None, когда dry_run=True)
    repository: PosterRepository,
) -> None:
    """
    Генерирует постер ровно для одного фильма, заданного через --film-id.

    Загружает title, genre, description, release_year, rating из Sakila.
    Завершается с кодом 1, если фильм не найден.
    Откатывается на title+genre, если description пустое — НЕ выдумывает контент.
    """
    film = _fetch_film_by_id(args.film_id)
    if film is None:
        print(f"\n[ОШИБКА] Film ID {args.film_id} не найден в Sakila.")
        sys.exit(1)

    desc, is_fallback = _build_description(film)
    if is_fallback:
        print(
            f"\n  [FALLBACK] У фильма {args.film_id} нет description в БД. "
            f"Используем title + genre."
        )

    prompt, negative_prompt = build_prompt(
        title=film['title'],
        genre=film.get('genre') or '',
        description=desc,
        style='auto',
    )

    _print_film_preview(film, prompt, negative_prompt, is_fallback)

    if args.dry_run:
        print(f"\n  [DRY-RUN] Вызов API не выполнен. Длина промпта: {len(prompt)} символов.")
        return

    if repository.openai_poster_exists(film['film_id']):
        print(f"\n  [SKIP] У фильма {args.film_id} уже есть завершённый постер OpenAI.")
        return

    print(f"\n  Генерируем постер для: {film['title']}")
    print("  (это может занять 20-30 секунд)")
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
        print(f"\n  [ОШИБКА] {exc}")
        sys.exit(1)


# ── Повтор неудачных элементов ────────────────────────────────────────────

def _run_retry_failed(args: argparse.Namespace, queue: GenerationQueue) -> None:
    """
    Явно сбрасывает неудачные элементы очереди обратно в 'pending'.

    С --film-id N : сбрасывает только этот фильм.
    Без --film-id : показывает количество неудачных элементов, затем сбрасывает все.

    НЕ вызывает OpenAI. НЕ создаёт файлы. НЕ пишет в movie_posters.
    """
    print(LINE)
    print("  ITCH Films — повтор неудачных элементов очереди")
    print(LINE)

    if args.film_id is not None:
        count = queue.retry_failed(film_id=args.film_id)
        if count:
            print(f"\n  [OK] film_id={args.film_id} сброшен: 'failed' → 'pending'.")
        else:
            print(
                f"\n  [SKIP] film_id={args.film_id} не был в статусе 'failed' "
                f"(уже pending / done / processing)."
            )
    else:
        total_failed = queue.count_by_status('failed')
        print(f"\n  Неудачных элементов в очереди: {total_failed}")
        if total_failed == 0:
            print("  Сбрасывать нечего.")
        else:
            count = queue.retry_failed()
            print(f"  [OK] Сброшено {count} элемент(ов): 'failed' → 'pending'.")

    print()
    print(LINE)
    print("  Вызовов OpenAI API не было.")
    print("  Файлы не создавались.")
    print("  Таблица movie_posters НЕ изменялась.")


# ── Синхронизация очереди ─────────────────────────────────────────────

def _run_sync_queue(
    repository: PosterRepository,
    queue: GenerationQueue,
) -> None:
    """
    Синхронизирует movie_generation_queue со статусом завершённых постеров OpenAI.

    Источник истины: movie_posters WHERE provider='openai' AND status='completed'.
    Фильмы с завершённым постером OpenAI → статус очереди 'done'.
    Все остальные фильмы                 → статус очереди 'pending'.
    Фильмы, отсутствующие в очереди      → INSERT как 'pending'.

    НЕ вызывает OpenAI API. НЕ пишет в movie_posters. НЕ создаёт файлы.
    """
    print(LINE)
    print("  ITCH Films — синхронизация очереди (источник истины: OpenAI)")
    print(LINE)

    print("\n[1/3] Получаем фильмы из Sakila (только чтение)...")
    films = _fetch_films()
    all_film_ids = [f['film_id'] for f in films]
    print(f"      Найдено {len(all_film_ids)} фильмов.")

    print("\n[2/3] Получаем ID завершённых постеров OpenAI (только чтение)...")
    openai_done_ids = repository.get_openai_completed_film_ids()
    print(f"      Завершённых постеров OpenAI      : {len(openai_done_ids)}")
    print(f"      Фильмов, требующих генерации      : {len(all_film_ids) - len(openai_done_ids)}")

    print("\n[3/3] Синхронизируем очередь...")
    result = queue.sync_for_openai_generation(all_film_ids, openai_done_ids)

    print()
    print(LINE)
    print("  Синхронизация завершена:")
    print(f"  Добавлено (новых записей) : {result['inserted']}")
    print(f"  Переведено в pending      : {result['set_to_pending']}")
    print(f"  Переведено в done         : {result['set_to_done']}")
    print(f"  Без изменений             : {result['unchanged']}")
    print(LINE)
    print()
    print("  Вызовов OpenAI API не было.")
    print("  Файлы не создавались.")
    print("  Таблица movie_posters НЕ изменялась.")


# ── Batch dry-run (только чтение) ─────────────────────────────────────────

def _run_batch_dry(args: argparse.Namespace, repository: PosterRepository) -> None:
    """
    Read-only предпросмотр dry-run для пакетного режима.

    Выполняет только SELECT-запросы — никогда не создаёт таблицы, не пишет в
    очередь, не вызывает OpenAI API и не создаёт файлы. Очередь генерации
    вообще не используется; кандидаты-фильмы берутся напрямую из Sakila.
    """
    print("\n[DRY-RUN] Получаем фильмы из Sakila (только чтение)...")
    films = _fetch_films()
    print(f"          Найдено {len(films)} фильмов в Sakila.")

    openai_done_ids = repository.get_openai_completed_film_ids()
    candidates = [f for f in films if f['film_id'] not in openai_done_ids]

    # Вычисляем действующий лимит для dry-run
    if getattr(args, 'target_from_db', False):
        dry_limit = len(candidates)
    else:
        dry_limit = args.limit
    if getattr(args, 'max_api_attempts', None) is not None:
        dry_limit = min(dry_limit, args.max_api_attempts)

    selected = candidates[:min(dry_limit, 10)]   # показываем не более 10 в dry-run

    print(f"          Фильмов с завершённым постером OpenAI : {len(openai_done_ids)}")
    print(f"          Фильмов без постера OpenAI            : {len(candidates)}")
    print(f"          Было бы сгенерировано до              : {dry_limit}")
    print(f"          Показываем предпросмотр для           : {len(selected)}")

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
    print("  [DRY-RUN] Таблицы не создавались. Очередь не менялась.")
    print("  [DRY-RUN] Вызовов OpenAI API не было. Файлы не записывались.")


# ── Batch-режим (боевой) ─────────────────────────────────────────────────

def _run_batch(
    args: argparse.Namespace,
    service,           # PosterService | None  (None, когда dry_run=True)
    repository: PosterRepository,
    queue: GenerationQueue,
) -> None:
    """
    Обрабатывает очередь генерации до --limit реальных генераций.

    В режиме dry-run сразу делегирует в _run_batch_dry(), который полностью
    read-only. Все операции с очередью и таблицами пропускаются.

    Логика пропуска (боевой режим): фильм пропускается, только если у него
    есть завершённый постер с provider='openai'. Пропуски НЕ считаются в --limit.
    Mock-постеры (provider='mock') НЕ препятствуют регенерации.
    """
    if args.dry_run:
        _run_batch_dry(args, repository)
        return

    # ── Шаг 1: таблицы ────────────────────────────────────────────────
    print("\n[1/4] Создаём таблицы...")
    repository.create_table()
    queue.create_table()
    print("      Готово.")


    # ── Шаг 2: получаем фильмы ───────────────────────────────────────────
    print("\n[2/4] Получаем фильмы из Sakila...")
    films = _fetch_films()
    all_film_ids = [f['film_id'] for f in films]
    film_lookup: dict[int, dict] = {f['film_id']: f for f in films}
    print(f"      Найдено {len(films)} фильмов.")

    # ── Шаг 3: синхронизация очереди (источник истины: завершённые постеры OpenAI) ─
    # Заменяет bulk_enqueue + reset_stuck_processing.
    # Фильмы с постером OpenAI → done; все остальные → pending (даже если done через mock).
    print("\n[3/4] Синхронизируем очередь со статусом постеров OpenAI...")
    openai_done_ids = repository.get_openai_completed_film_ids()
    sync_result     = queue.sync_for_openai_generation(all_film_ids, openai_done_ids)
    print(f"      Inserted        : {sync_result['inserted']}")
    print(f"      Set to pending  : {sync_result['set_to_pending']}")
    print(f"      Set to done     : {sync_result['set_to_done']}")
    print(f"      Unchanged       : {sync_result['unchanged']}")

    # ── Вычисляем действующий лимит (--target-from-db / --max-api-attempts) ──
    remaining_films = len(all_film_ids) - len(openai_done_ids)

    if getattr(args, 'target_from_db', False):
        effective_limit = remaining_films
        print(f"\n      [target-from-db] Осталось фильмов: {remaining_films}")
    else:
        effective_limit = args.limit

    if getattr(args, 'max_api_attempts', None) is not None:
        effective_limit = min(effective_limit, args.max_api_attempts)
        print(f"      [max-api-attempts] Применён жёсткий предел: {args.max_api_attempts}")

    # ── Предварительная проверка бюджета ──────────────────────────────────────────────
    cost_per_img   = getattr(args, 'cost_per_image', DEFAULT_COST_PER_IMG)
    budget_limit   = getattr(args, 'estimated_budget', None)
    retry_reserve  = min(int(effective_limit * 0.10), 100)
    max_attempts   = effective_limit + retry_reserve
    estimated_cost = max_attempts * cost_per_img

    print(f"\n      Оценка бюджета:")
    print(f"        cost_per_image     = ${cost_per_img:.4f}")
    print(f"        effective_limit    = {effective_limit}")
    print(f"        retry_reserve      = {retry_reserve}")
    print(f"        max_api_attempts   = {max_attempts}")
    print(f"        estimated_max_cost = ${estimated_cost:.2f}")
    if budget_limit is not None:
        print(f"        budget_limit       = ${budget_limit:.2f}")
        if estimated_cost > budget_limit:
            print(
                f"\n[ПРЕРВАНО ПО БЮДЖЕТУ] Оценочная стоимость ${estimated_cost:.2f} "
                f"превышает бюджет ${budget_limit:.2f}.\n"
                f"  Используйте --max-api-attempts, чтобы задать безопасный предел.\n"
                f"  Безопасный предел: --max-api-attempts {int(budget_limit / cost_per_img)}"
            )
            sys.exit(1)
    elif estimated_cost > BUDGET_HARD_LIMIT:
        print(
            f"\n[ПРЕДУПРЕЖДЕНИЕ О БЮДЖЕТЕ] Оценка ${estimated_cost:.2f} "
            f"превышает жёсткий лимит ${BUDGET_HARD_LIMIT:.2f}.\n"
            f"  Используйте --estimated-budget, чтобы явно разрешить, "
            f"или --max-api-attempts, чтобы ограничить.\n"
            f"  Безопасный предел: --max-api-attempts {int(BUDGET_HARD_LIMIT / cost_per_img)}"
        )
        sys.exit(1)

    # ── Шаг 4: обрабатываем очередь — останавливаемся, когда api_attempts достигает предела ──
    api_cap = effective_limit   # максимум реальных вызовов OpenAI API
    print(f"\n[4/4] Генерируем постеры (api_cap={api_cap})...")
    generated   = 0    # успешные генерации
    skipped     = 0    # фильмы, у которых уже был постер OpenAI
    failed      = 0    # неудачные генерации
    api_attempts = 0   # реальные вызовы OpenAI Images API (успех + неудача)

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
                # Без вызова API — просто помечаем элемент очереди как неудачный и идём дальше
                queue.mark_failed(queue_id)
                failed += 1
                print(f"  [MISSING ] [{film_id:>4}] фильм не найден в Sakila")
                continue

            # Пропускаем, если постер OpenAI уже существует — mock-постеры не считаются
            if repository.openai_poster_exists(film_id):
                queue.mark_done(queue_id)
                skipped += 1
                continue   # пропуски НЕ считаются в api_attempts

            desc, is_fallback = _build_description(film)

            queue.mark_processing(queue_id)
            start = time.monotonic()
            api_attempts += 1   # увеличиваем здесь — считаем этот реальный вызов OpenAI API
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

                # Отчёт о прогрессе каждые 50 успешных генераций
                if generated % 50 == 0:
                    valid_now  = len(openai_done_ids) + generated
                    left_now   = len(all_film_ids) - valid_now
                    api_cost   = round(api_attempts * cost_per_img, 4)
                    print()
                    print(f"  ── Прогресс ────────────────────────────────────")
                    print(f"  Фильмов в Sakila          : {len(all_film_ids)}")
                    print(f"  Валидных постеров было    : {len(openai_done_ids)}")
                    print(f"  Сгенерировано в этом запуске : {generated}")
                    print(f"  Текущий валидный итог     : {valid_now}")
                    print(f"  Осталось                  : {left_now}")
                    print(f"  Попыток API               : {api_attempts}")
                    print(f"  Неудачных попыток         : {failed}")
                    print(f"  Оценочная стоимость       : ~${api_cost:.4f}")
                    print(f"  ────────────────────────────────────────────────")
                    print()

            except Exception as exc:
                queue.mark_failed(queue_id)
                failed += 1
                print(
                    f"  [FAILED   ] [{film_id:>4}] "
                    f"{film['title'][:40]:<40}  {exc}"
                )

    # ── Финальная статистика очереди ─────────────────────────────────────────────
    print("\n[Итог] Статус очереди:")
    for status, count in sorted(queue.get_stats().items()):
        print(f"        {status:<12}: {count}")

    actual_cost = round(api_attempts * cost_per_img, 4)
    print(f"\n[Итог] Попыток API за этот запуск : {api_attempts}")
    print(f"[Итог] Оценочная стоимость        : ~${actual_cost:.4f}")

    _print_summary(generated, skipped, failed, len(films))


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # --sync-queue, --retry-failed и --dry-run не вызывают API.
    # Провайдер создаётся только для боевой генерации (batch или single-film).
    provider = None
    model    = os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_MODEL)
    needs_provider = not args.dry_run and not args.sync_queue and not args.retry_failed
    if needs_provider:
        try:
            provider = OpenAIProvider()
            model    = provider.model_name()
        except ProviderConfigurationError as exc:
            print(f"\n[ОШИБКА КОНФИГУРАЦИИ] {exc}")
            print("  Добавьте OPENAI_API_KEY в файл .env.")
            sys.exit(1)

    storage    = PosterStorage(STORAGE_DIR)
    repository = PosterRepository()
    queue      = GenerationQueue()
    service    = (
        PosterService(provider=provider, storage=storage, repository=repository)
        if provider else None
    )

    # Служебные команды: выход до баннера и генерации
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
