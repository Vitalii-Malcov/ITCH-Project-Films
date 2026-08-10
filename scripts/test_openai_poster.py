"""
scripts/test_openai_poster.py
──────────────────────────────────────────────────────────────────────────────
One-shot manual test for OpenAIProvider.

What it does:
    1. Loads .env (reads OPENAI_API_KEY and optional overrides).
    2. Creates OpenAIProvider with the configured model and settings.
    3. Builds a prompt for ACADEMY DINOSAUR via the existing prompt_builder.
    4. Generates exactly ONE image.
    5. Saves it to storage/posters/ via PosterStorage.

What it does NOT do:
    - Does NOT write to any database (movie_posters table is untouched).
    - Does NOT add anything to the generation queue.
    - Does NOT touch existing 1106 generated posters.
    - Does NOT print the API key, not even masked.

Usage (run from project root):
    python scripts/test_openai_poster.py

Expected output:
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

# ── Path setup ────────────────────────────────────────────────────────────────
_script_dir   = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_itch_films   = os.path.join(_project_root, "itch_films")

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _itch_films not in sys.path:
    sys.path.insert(0, _itch_films)

from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, ".env"))

from services.ai_posters.providers.openai_provider import OpenAIProvider, DEFAULT_MODEL
from services.ai_posters.poster_storage import PosterStorage
from services.ai_posters.prompt_builder import build_prompt
from services.ai_posters.exceptions import ProviderConfigurationError, ProviderError

STORAGE_DIR = os.path.join(_project_root, "storage", "posters")
LINE = "=" * 52

TEST_FILM = {
    "title":       "ACADEMY DINOSAUR",
    "genre":       "Documentary",
    "description": "A documentary about a dinosaur academy and an epic battle.",
    "style":       "auto",
}


def main() -> None:
    print(LINE)
    print("  OpenAI Provider — Single Poster Test")
    print(LINE)

    # ── 1. Check key presence — never reveal the value ────────────────────────
    key = os.getenv("OPENAI_API_KEY", "")
    print(f"\n  API key      : {'configured' if key else 'MISSING'}")
    if not key:
        print("\n[ERROR] OPENAI_API_KEY is not set in .env")
        print("  Add: OPENAI_API_KEY=sk-...")
        sys.exit(1)

    # ── 2. Create provider ────────────────────────────────────────────────────
    try:
        provider = OpenAIProvider()
    except ProviderConfigurationError as exc:
        print(f"\n[CONFIG ERROR] {exc}")
        sys.exit(1)

    # Derive active size for reporting
    portrait_size = provider._map_size(640, 960)

    print(f"  Provider     : {provider.provider_name()}")
    print(f"  Model        : {provider.model_name()}")
    print(f"  Quality      : {provider._quality}")
    print(f"  Size         : {portrait_size}")
    print(f"  Format       : {provider._output_fmt}")
    print(f"  Compression  : {provider._compression}")

    # ── 3. Build prompt ───────────────────────────────────────────────────────
    prompt, negative_prompt = build_prompt(
        title=TEST_FILM["title"],
        genre=TEST_FILM["genre"],
        description=TEST_FILM["description"],
        style=TEST_FILM["style"],
    )
    print(f"\n  Prompt ({len(prompt)} chars):")
    print(f"  {prompt[:200]}...")

    # ── 4. Generate one image ─────────────────────────────────────────────────
    print(f"\n  Generating poster for: {TEST_FILM['title']}")
    print("  (this may take 5–15 seconds)")
    start = time.monotonic()

    try:
        image_bytes = provider.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
        )
    except ProviderConfigurationError as exc:
        print(f"\n[CONFIG ERROR] {exc}")
        sys.exit(1)
    except ProviderError as exc:
        print(f"\n[PROVIDER ERROR] {exc}")
        sys.exit(1)

    elapsed = round(time.monotonic() - start, 2)

    # ── 5. Save file (no DB record) ───────────────────────────────────────────
    storage = PosterStorage(STORAGE_DIR)
    filename = storage.save(image_bytes)
    path = storage.get_path(filename)

    # ── 6. Report ─────────────────────────────────────────────────────────────
    print()
    print(LINE)
    print(f"  Saved to    : {path}")
    print(f"  Filename    : {filename}")
    print(f"  File size   : {len(image_bytes):,} bytes")
    print(f"  Time        : {elapsed}s")
    print(f"  Model       : {provider.model_name()}")
    print(LINE)
    print()
    print("  [OK] Test poster generated.")
    print("  NOTE: file is NOT recorded in movie_posters table.")
    print(f"  Open: {path}")


if __name__ == "__main__":
    main()