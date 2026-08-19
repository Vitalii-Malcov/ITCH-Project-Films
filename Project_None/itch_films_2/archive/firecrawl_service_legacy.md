# firecrawl_service_legacy — Историческая справка

Это первая версия сервиса Firecrawl, написанная до выделения модуля `services/firecrawl/`.

## Причины замены

1. **Глобальный клиент при импорте** — `FirecrawlApp(api_key=...)` создавался сразу при загрузке модуля. Если ключ отсутствовал, Flask не запускался вообще.
2. **Нет обработки ошибок** — любая сетевая проблема давала необработанное исключение.
3. **Устаревший класс SDK** — `FirecrawlApp` в `firecrawl-py` v4.31.0 стал заглушкой без метода `scrape_url`. Рабочей реализацией является `V1FirecrawlApp`.
4. **Захардкоженный API-ключ** — ключ был в исходном коде, а не в переменных окружения.

## Что пришло на замену

Модуль `services/firecrawl/` с четырьмя файлами:

| Файл | Назначение |
|---|---|
| `client.py` | `FirecrawlClient` с методами `scrape`, `crawl`, `search` |
| `models.py` | Dataclass-модели результатов (`FirecrawlResult`, `CrawlResult`, `SearchResult`) |
| `exceptions.py` | Иерархия исключений (`FirecrawlError` и подклассы) |
| `__init__.py` | Публичный API модуля |

## Оригинальный код (неработающий исторический пример)

```python
# НЕ ИСПОЛЬЗОВАТЬ. Хранится только как историческая справка.
# FirecrawlApp устарел в firecrawl-py v4.31.0 — метода scrape_url нет.

import os
from dotenv import load_dotenv
from firecrawl import FirecrawlApp  # устарел в v4.31.0

load_dotenv()

api_key = os.getenv("FIRECRAWL_API_KEY")

if not api_key:
    raise RuntimeError("Переменная окружения FIRECRAWL_API_KEY не задана")

app = FirecrawlApp(api_key=api_key)


def scrape_page(url: str):
    result = app.scrape_url(url)  # AttributeError в v4.31.0
    return result.markdown


if __name__ == "__main__":
    text = scrape_page("https://example.com")
    print(text)
```