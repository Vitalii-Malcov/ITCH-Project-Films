# Project Architecture — Firecrawl API Service

**Stack:** Python 3.11+ · Flask 3.1 · MongoDB 7 · firecrawl-py 4.31 · pytest 9.1
**Точка входа:** `python run.py` (из папки `itch_films_2/`)
**Режим отладки:** управляется через `FLASK_DEBUG=true` в `.env`

> Этот проект — самостоятельный Firecrawl API-сервис, живёт в папке
> `itch_films_2/` рядом с другим независимым проектом `itch_films/`
> (оба — подпапки `Project_IT_Career_Hub_2/`; название `itch_films_2` — просто
> имя папки, к каталогу фильмов ITCH Films отношения не имеет). У ITCH Films свой `run.py`,
> свои зависимости, своя документация (см. `itch_films/PROJECT_ARCHITECTURE.md`).
> ITCH Films держит собственную урезанную копию Firecrawl-клиента
> (`itch_films/services/firecrawl/`) для одной своей фичи («Подробнее» на
> карточке фильма) — это не зависимость от этого проекта.

---

## Структура файлов

```
Project_IT_Career_Hub_2\
├── itch_films\                    # Другой независимый проект (см. его README)
└── itch_films_2\                  # Этот проект (Firecrawl API-сервис)
    ├── run.py                       # Точка входа Flask-приложения
    ├── pytest.ini                   # Конфигурация pytest (testpaths=tests)
    ├── requirements.txt             # Production зависимости
    ├── requirements-dev.txt         # Dev зависимости (pytest)
    ├── .env                         # Секреты — НЕ коммитить
    ├── .env.example                 # Пример переменных окружения
    ├── app/                         # Flask-приложение
    │   ├── __init__.py              # create_app() — регистрирует firecrawl_bp
    │   └── routes/
    │       ├── __init__.py          # Реэкспортирует firecrawl_bp
    │       └── firecrawl.py         # Flask Blueprint /api — scrape/crawl/search/history
    ├── services/
    │   ├── firecrawl/               # Изолированный слой интеграции Firecrawl
    │   │   ├── __init__.py          # Публичный API: 3 модели + 5 исключений + 1 клиент
    │   │   ├── client.py            # FirecrawlClient — scrape(), crawl(), search()
    │   │   ├── models.py            # FirecrawlResult, CrawlResult, SearchResult (dataclass)
    │   │   └── exceptions.py        # Иерархия исключений FirecrawlError
    │   └── mongo/
    │       ├── __init__.py
    │       └── client.py            # MongoService — сохранение и чтение результатов
    ├── scripts/
    │   └── check_firecrawl.py       # Ручная проверка Firecrawl API (не тест pytest)
    ├── tests/
    │   ├── conftest.py              # Shared fixtures: app, client (from app import create_app)
    │   ├── test_routes.py           # Тесты Flask маршрутов (MongoDB и Firecrawl замокированы)
    │   └── test_firecrawl_client.py # Unit-тесты FirecrawlClient (V1FirecrawlApp замокирован)
    └── archive/
        └── firecrawl_service_legacy.md  # Исторический пример первой реализации
```

## Маршруты Flask API

| Метод | URL | Описание |
|---|---|---|
| GET | `/` | Заглушка — JSON со статусом и списком эндпоинтов (сервис без HTML-страниц) |
| POST | `/api/scrape` | Скрейпит одну страницу → `FirecrawlResult` |
| POST | `/api/crawl` | Обходит сайт → `CrawlResult` |
| POST | `/api/search` | Веб-поиск → `SearchResult` |
| POST | `/api/extract` | Зарезервирован, возвращает 501 |
| GET | `/api/history/<collection>` | Читает историю из MongoDB |

## Сервисный слой Firecrawl

**Зачем изолирован:** приложение никогда не работает напрямую с `firecrawl-py`. Если SDK сменит API (уже произошло в v4.31.0: `FirecrawlApp` → `V1FirecrawlApp`), меняется только `services/firecrawl/`, а маршруты остаются нетронутыми.

**Откуда берётся API key:** исключительно через `FIRECRAWL_API_KEY` в `.env`. Никогда в исходном коде. `FirecrawlClient.__init__` читает переменную через `os.getenv()` после `load_dotenv()`. При отсутствии ключа поднимает `FirecrawlConfigurationError`.

**Исключения:**

| Класс | HTTP-статус | Причина |
|---|---|---|
| `FirecrawlConfigurationError` | 503 | API ключ не задан |
| `FirecrawlValidationError` | 400 | Некорректный URL или параметры |
| `FirecrawlRateLimitError` | 429 | Превышен лимит API |
| `FirecrawlConnectionError` | 503 | Сетевая ошибка |
| `FirecrawlError` | 500 | Прочие ошибки SDK |

## Тесты

**`scripts/check_firecrawl.py`** — ручная проверка. Делает реальный HTTP-запрос к `https://example.com`. Требует `.env` с реальным ключом. Запуск: `python scripts/check_firecrawl.py`.

**`tests/`** — автоматические pytest-тесты. Не обращаются к реальной сети и БД:
- `V1FirecrawlApp` заменён `MagicMock` в тестах клиента
- `MongoService` заменён `MagicMock` в тестах маршрутов
- `load_dotenv` патчится там, где нужно проверить отсутствие ключа
- `.env` не загружается в тестах намеренно

Запуск: `python -m pytest -v`

## Переменные окружения

```env
FIRECRAWL_API_KEY=your_firecrawl_api_key   # обязательна для Firecrawl
MONGO_URI=mongodb://localhost:27017/        # MongoDB URI
MONGO_DB_NAME=it_career_hub                # имя базы данных
FLASK_DEBUG=false                           # true только для разработки
```

## Базы данных

### MongoDB (запись и чтение)

```
База: it_career_hub
  └── Коллекции: scrapes, searches, crawls
```

Хост: `localhost:27017` · Создаётся автоматически при первом запросе.

## Принципы архитектуры

- **Separation of concerns** — маршруты не работают напрямую с SDK, только через `services/firecrawl`.
- **Fail-safe MongoDB** — недоступность MongoDB не должна ронять API (см. `MongoService`).
- **Параметризованный доступ к MongoDB** — `ALLOWED_COLLECTIONS` whitelist на `/api/history/<collection>`.
- **Секреты только в `.env`** — никогда в исходном коде, `.env` в `.gitignore`.
