"""
Ручная проверка модуля services.firecrawl.
Запуск: python scripts/check_firecrawl.py
        python -m scripts.check_firecrawl

Это НЕ автоматический тест. Требует реального API ключа в .env.
"""

import sys
from pathlib import Path

# Позволяет запускать скрипт напрямую: python scripts/check_firecrawl.py
# Path(__file__).resolve().parent.parent — корень проекта (на уровень выше scripts/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from services.firecrawl import (
    FirecrawlClient,
    FirecrawlConfigurationError,
    FirecrawlConnectionError,
    FirecrawlError,
    FirecrawlRateLimitError,
    FirecrawlValidationError,
)

TARGET_URL = "https://example.com"


def main() -> int:
    print("=== Firecrawl Manual Check ===\n")

    try:
        client = FirecrawlClient()
        print("Client initialized.\n")

        result = client.scrape(TARGET_URL)

        print(f"URL:   {result.url}")
        print(f"Title: {result.title}")
        print(f"\nMarkdown (first 300 chars):\n{result.markdown[:300]}")
        print("\n[OK] Check passed.")
        return 0

    except FirecrawlConfigurationError as e:
        print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        return 2
    except FirecrawlValidationError as e:
        print(f"[VALIDATION ERROR] {e}", file=sys.stderr)
        return 5
    except FirecrawlRateLimitError as e:
        print(f"[RATE LIMIT] {e}", file=sys.stderr)
        return 3
    except FirecrawlConnectionError as e:
        print(f"[CONNECTION ERROR] {e}", file=sys.stderr)
        return 4
    except FirecrawlError as e:
        print(f"[FIRECRAWL ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())