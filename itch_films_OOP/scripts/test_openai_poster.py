"""
scripts/test_openai_poster.py
──────────────────────────────────────────────────────────────────────────────
Разовый ручной тест OpenAIProvider.

Что делает:
    1. Загружает .env (читает OPENAI_API_KEY и опциональные переопределения).
    2. Создаёт OpenAIProvider с настроенной моделью и параметрами.
    3. Строит промпт для ACADEMY DINOSAUR через существующий prompt_builder.
    4. Генерирует ровно ОДНО изображение.
    5. Сохраняет его в storage/posters/ через PosterStorage.

Чего НЕ делает:
    - НЕ пишет ни в какую базу данных (таблица movie_posters не затрагивается).
    - НЕ добавляет ничего в очередь генерации.
    - НЕ трогает уже сгенерированные ранее постеры (файлы на диске и
      строки в movie_posters от прошлых запусков остаются нетронутыми).
    - НЕ печатает API-ключ, даже замаскированным.

Использование (запуск из корня проекта):
    python scripts/test_openai_poster.py

Ожидаемый вывод:
    ====================================================
      OpenAI Provider — Single Poster Test
    ====================================================
      API key      : configured
      Provider     : openai
      Model        : gpt-image-2
      Quality      : low
      Size         : 1024x1536
      Format       : webp
      Compression  : 80

      Prompt (N chars): ...
      Generating...

    ====================================================
      Saved to    : D:\\...\\storage\\posters\\001107.webp
      Filename    : 001107.webp
      File size   : 45,231 bytes
      Time        : 8.42s
      Model       : gpt-image-2
    ====================================================
      [OK] Test poster generated. NOT saved to database.
"""

import os
import sys
import time

# ── Настройка путей ────────────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
_itch_films = os.path.dirname(_script_dir)

if _itch_films in sys.path:
    sys.path.remove(_itch_films)
sys.path.insert(0, _itch_films)

from dotenv import load_dotenv
load_dotenv(os.path.join(_itch_films, ".env"))

from services.ai_posters.providers.openai_provider import OpenAIProvider, DEFAULT_MODEL
from services.ai_posters.poster_storage import PosterStorage
from services.ai_posters.prompt_builder import build_prompt
from services.ai_posters.exceptions import ProviderConfigurationError, ProviderError

STORAGE_DIR = os.path.join(_itch_films, "storage", "posters")
LINE = "=" * 52

TEST_FILM = {
    "title":       "ACADEMY DINOSAUR",
    "genre":       "Documentary",
    "description": "A documentary about a dinosaur academy and an epic battle.",
    "style":       "auto",
}


def main() -> None:
    print(LINE)
    print("  OpenAI Provider — тест генерации одного постера")
    print(LINE)

    # ── 1. Проверяем наличие ключа — никогда не показываем значение ────────────
    key = os.getenv("OPENAI_API_KEY", "")
    print(f"\n  API key      : {'настроен' if key else 'ОТСУТСТВУЕТ'}")
    if not key:
        print("\n[ОШИБКА] OPENAI_API_KEY не задан в .env")
        print("  Добавьте: OPENAI_API_KEY=sk-...")
        sys.exit(1)

    # ── 2. Создаём провайдера ────────────────────────────────────────────────────
    try:
        provider = OpenAIProvider()
    except ProviderConfigurationError as exc:
        print(f"\n[ОШИБКА КОНФИГУРАЦИИ] {exc}")
        sys.exit(1)

    # Вычисляем активный размер для отчёта
    portrait_size = provider._map_size(640, 960)

    print(f"  Provider     : {provider.provider_name()}")
    print(f"  Model        : {provider.model_name()}")
    print(f"  Quality      : {provider._quality}")
    print(f"  Size         : {portrait_size}")
    print(f"  Format       : {provider._output_fmt}")
    print(f"  Compression  : {provider._compression}")

    # ── 3. Строим промпт ───────────────────────────────────────────────────────
    prompt, negative_prompt = build_prompt(
        title=TEST_FILM["title"],
        genre=TEST_FILM["genre"],
        description=TEST_FILM["description"],
        style=TEST_FILM["style"],
    )
    print(f"\n  Промпт ({len(prompt)} символов):")
    print(f"  {prompt[:200]}...")

    # ── 4. Генерируем одно изображение ─────────────────────────────────────────────────
    print(f"\n  Генерируем постер для: {TEST_FILM['title']}")
    print("  (это может занять 5–15 секунд)")
    start = time.monotonic()

    try:
        image_bytes = provider.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
        )
    except ProviderConfigurationError as exc:
        print(f"\n[ОШИБКА КОНФИГУРАЦИИ] {exc}")
        sys.exit(1)
    except ProviderError as exc:
        print(f"\n[ОШИБКА ПРОВАЙДЕРА] {exc}")
        sys.exit(1)

    elapsed = round(time.monotonic() - start, 2)

    # ── 5. Сохраняем файл (без записи в БД) ───────────────────────────────────────────
    storage = PosterStorage(STORAGE_DIR)
    filename = storage.save(image_bytes)
    path = storage.get_path(filename)

    # ── 6. Отчёт ─────────────────────────────────────────────────────────────
    print()
    print(LINE)
    print(f"  Saved to    : {path}")
    print(f"  Filename    : {filename}")
    print(f"  File size   : {len(image_bytes):,} bytes")
    print(f"  Time        : {elapsed}s")
    print(f"  Model       : {provider.model_name()}")
    print(LINE)
    print()
    print("  [OK] Тестовый постер сгенерирован.")
    print("  ПРИМЕЧАНИЕ: файл НЕ записан в таблицу movie_posters.")
    print(f"  Открыть: {path}")


if __name__ == "__main__":
    main()
