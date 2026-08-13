# Project Architecture — IT Career Hub 2

> **Документ содержит два раздела:**
> 1. **IT Career Hub 2** (текущий проект, корень репозитория) — Flask Blueprint (`firecrawl_app/`) + Firecrawl + MongoDB.
> 2. **ITCH Films Premium** (субпроект `itch_films/`) — каталог фильмов Flask + MySQL + MongoDB + AI-постеры (OpenAI).
> С 2026-08-13 это **один Flask-процесс с одной точкой входа** — `itch_films/run.py`.
> Корневой `firecrawl_app/` больше не самостоятельное приложение: он подключается как
> blueprint внутри `itch_films/app/__init__.py`, поэтому Firecrawl-эндпоинты (`/api/scrape`,
> `/api/crawl`, `/api/search`, `/api/history/<collection>`) и маршруты ITCH Films (`/`,
> `/search`, `/stats`, ...) обслуживаются одним сервером на одном порту. Отдельного
> корневого `run.py` больше нет — он удалён при слиянии.

---

## IT Career Hub 2 / Firecrawl — Текущая архитектура

**Stack:** Python 3.11+ · Flask 3.1 · MongoDB 7 · firecrawl-py 4.31 · pytest 9.1
**Точка входа:** `python itch_films/run.py` — единственная для всего проекта (см. баннер выше)
**Режим отладки:** управляется через `FLASK_DEBUG=true` в `.env`

### Структура файлов

```
D:\Project_IT_Career_Hub_2\
├── pytest.ini                   # Конфигурация pytest (testpaths=tests)
├── requirements.txt             # Production зависимости
├── requirements-dev.txt         # Dev зависимости (pytest)
├── .env                         # Секреты — НЕ коммитить
├── .env.example                 # Пример переменных окружения
├── firecrawl_app/                # Пакет переименован из app/ 2026-08-13, чтобы не
│   │                              # конфликтовать с itch_films/app/ (оба назывались
│   │                              # "app" — Python не может импортировать два модуля
│   │                              # с одинаковым именем одновременно). Сам по себе
│   │                              # больше не запускается — только как blueprint.
│   ├── __init__.py              # create_app() — используется тестами (tests/conftest.py)
│   │                             # для изолированного Flask test client
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
│   ├── conftest.py              # Shared fixtures: app, client (from firecrawl_app import create_app)
│   ├── test_routes.py           # Тесты Flask маршрутов (MongoDB и Firecrawl замокированы)
│   └── test_firecrawl_client.py # Unit-тесты FirecrawlClient (V1FirecrawlApp замокирован)
└── archive/
    └── firecrawl_service_legacy.md  # Исторический пример первой реализации
```

**Важно:** `firecrawl_app.create_app()` — это отдельное Flask-приложение только для
изолированных pytest-тестов (`tests/`). В продакшене (`python itch_films/run.py`)
Firecrawl работает не через `create_app()`, а через `firecrawl_bp`, подключённый
напрямую в `itch_films/app/__init__.py` (см. раздел ITCH Films ниже). Маршруты и
поведение идентичны в обоих случаях — отличается только то, какой Flask-объект
их хостит.

### Маршруты Flask API

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/scrape` | Скрейпит одну страницу → `FirecrawlResult` |
| POST | `/api/crawl` | Обходит сайт → `CrawlResult` |
| POST | `/api/search` | Веб-поиск → `SearchResult` |
| POST | `/api/extract` | Зарезервирован, возвращает 501 |
| GET | `/api/history/<collection>` | Читает историю из MongoDB |

### Сервисный слой Firecrawl

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

### Тесты

**`scripts/check_firecrawl.py`** — ручная проверка. Делает реальный HTTP-запрос к `https://example.com`. Требует `.env` с реальным ключом. Запуск: `python scripts/check_firecrawl.py`.

**`tests/`** — автоматические pytest-тесты. Не обращаются к реальной сети и БД:
- `V1FirecrawlApp` заменён `MagicMock` в тестах клиента
- `MongoService` заменён `MagicMock` в тестах маршрутов
- `load_dotenv` патчится там, где нужно проверить отсутствие ключа
- `.env` не загружается в тестах намеренно

Запуск: `python -m pytest -v`

### Переменные окружения

```env
FIRECRAWL_API_KEY=your_firecrawl_api_key   # обязательна для Firecrawl
MONGO_URI=mongodb://localhost:27017/        # MongoDB URI
MONGO_DB_NAME=it_career_hub                # имя базы данных
FLASK_DEBUG=false                           # true только для разработки
```

---

## ITCH Films Premium — каталог фильмов с AI-постерами (`itch_films/`)

> Раздел ниже описывает субпроект в папке `itch_films/`. **С 2026-08-13 `itch_films/run.py`
> — единственная точка входа всего репозитория**, не только этого субпроекта: он поднимает
> один Flask-процесс, который обслуживает и каталог фильмов, и Firecrawl API (см. баннер
> в начале документа и структуру `app/__init__.py` ниже). Обновлено 2026-08-13.

---

# Project Architecture — ITCH Films Premium

**Stack:** Python 3.14 · Flask 3.0.3 · MySQL (Sakila, read-only) · MongoDB 7.0.37 · OpenAI Images API (`gpt-image-2`) · Firecrawl · Bootstrap 5

---

## Структура файлов

```
itch_films/
├── run.py                   # Единственная точка входа всего проекта — python itch_films/run.py
├── local_settings.py        # Настройки подключения (MySQL read/write, MongoDB, SECRET_KEY)
├── requirements.txt         # Зависимости: Flask, mysql-connector-python, pymongo
└── app/
    ├── __init__.py          # Создаёт Flask-приложение, настраивает sys.path на корень
    │                        # проекта, грузит .env, подключает firecrawl_bp (blueprint
    │                        # из корневого firecrawl_app/) и свои routes — в этом порядке
    ├── routes.py            # URL-маршруты: /, /search, /gallery, /stats, /api/*
    ├── mysql_connector.py   # Все SQL-запросы к Sakila (film, category, film_category)
    ├── mongo_logger.py      # Запись поисков в MongoDB
    ├── log_stats.py         # Чтение статистики из MongoDB
    ├── film_news.py         # Обёртка над services/firecrawl — get_film_news(title)
    ├── movie_images.py      # УСТАРЕЛО: старая формула Unsplash-URL. Файл остался
    │                        # на диске, но нигде не импортируется — заменён на
    │                        # services/ai_posters/ (см. ниже). Кандидат на удаление.
    ├── static/css/
    │   └── style.css        # Glassmorphism, dark theme, анимации
    └── templates/
        ├── base.html        # Базовый шаблон (навигация, Bootstrap 5)
        ├── index.html       # Главная страница и результаты поиска
        ├── gallery.html      # Галерея всех AI-постеров, 24 на страницу
        └── stats.html        # Страница статистики MongoDB
```

**AI-постеры живут в корне проекта, не в `itch_films/`** — общий модуль для CLI-скрипта и Flask-приложения:

```
services/ai_posters/
├── __init__.py
├── providers/
│   ├── base.py              # AIImageProvider — абстрактный интерфейс (Strategy pattern)
│   ├── openai_provider.py   # OpenAIProvider — gpt-image-2, quality=low, 1024×1536 → WebP
│   └── mock.py               # MockProvider — однотонный WebP без внешнего API (fallback)
├── prompt_builder.py         # build_prompt(title, genre, description) → (prompt, negative_prompt)
├── poster_service.py         # PosterService — оркестрирует prompt → generate → save
├── poster_storage.py         # PosterStorage — пишет WebP в storage/posters/
├── poster_repository.py      # PosterRepository — CRUD таблицы movie_posters (write DB)
├── queue.py                  # GenerationQueue — таблица movie_generation_queue
└── exceptions.py             # Иерархия исключений (ProviderError, RepositoryError, ...)

scripts/generate_movie_posters.py   # CLI: массовая генерация через OpenAIProvider,
                                     # бюджетные флаги (--estimated-budget, --max-api-attempts)
```

`services/ai_posters` (как и `firecrawl_app/`) становится импортируемым благодаря
`sys.path.insert()` в **`app/__init__.py`** — раньше этот хак жил прямо в `routes.py`
(отмечен там как `TODO`), 2026-08-13 перенесён в единую точку инициализации, до импорта
любых маршрутов, как и предполагал исходный `TODO`.

---

## Маршруты (`routes.py`)

| Метод | URL | Описание |
|---|---|---|
| GET | `/` | Главная страница, форма поиска |
| GET | `/search` | Поиск по названию/жанру/году; постеры подмешиваются из `movie_posters` |
| GET | `/api/suggest` | JSON-автокомплит, до 5 фильмов |
| GET | `/api/film/news?title=...` | Firecrawl-поиск доп. информации о фильме |
| GET | `/gallery` | Галерея всех 1001 постеров, пагинация по 24 |
| POST | `/api/poster/regenerate` | Перегенерация одного постера через `MockProvider` — без вызова OpenAI, без затрат |
| GET | `/posters/<filename>` | Отдаёт WebP-файл из `storage/posters/` |
| GET | `/stats`, `/stats/searches`, `/stats/unique` | Статистика поисков из MongoDB |

---

## Поток 1 — Поиск и отображение фильмов

```
Пользователь
     │  GET /search?q=alien  или  GET /search?genre=Action
     ▼
routes.py  — читает параметры запроса (q, genre)
     │
     ├─► mysql_connector.py ──► MySQL (Sakila DB, read-only)
     │       search_movies_by_title()          SELECT film_id, title,
     │       search_movies_by_genre()          release_year, rating,
     │                                         length, genre
     │       Возвращает: список словарей
     │
     ├─► _enrich_with_posters() ──► PosterRepository.get_latest_by_film_ids()
     │       Один JOIN-запрос на всю страницу результатов:
     │       SELECT mp.* FROM movie_posters mp
     │       INNER JOIN (SELECT film_id, MAX(id) FROM movie_posters
     │                    WHERE status='completed' GROUP BY film_id) latest
     │       ON mp.id = latest.max_id
     │       Фильмы без записи получают DEFAULT_POSTER (placeholder)
     │
     ├─► mongo_logger.py ──► MongoDB
     │       log_search(type, value, genre, results_count)
     │       Записывает документ в коллекцию search_logs
     │
     ▼
HTML Templates (index.html + base.html)
     │  Jinja2: render_template("index.html", movies=..., genres=...)
     ▼
Пользователь видит карточки фильмов с AI-постерами
```

---

## Поток 2 — Логирование и статистика

```
Пользователь
     │  Вводит поисковый запрос
     ▼
Поиск фильма  (routes.py → /search)
     │
     ▼
mongo_logger.py
     │  log_search(search_type, search_value, genre,
     │             year_from, year_to, results_count)
     │
     ▼
MongoDB  (база: itch_films_logs, коллекция: search_logs)
     │  Документ: { timestamp, search_type, search_value,
     │              genre, year_from, year_to, results_count }
     │
     │                    (позже, при переходе на /stats)
     ▼
log_stats.py
     │  get_popular_searches(limit=5)
     │      Aggregation Pipeline:
     │      $match → $group → $sort → $limit
     │
     │  get_recent_searches(limit=5)
     │      find().sort("timestamp", DESCENDING).limit(5)
     │
     ▼
/stats  (routes.py → stats.html)
     │  render_template("stats.html",
     │                  popular=popular, recent=recent)
     ▼
Пользователь видит топ-5 популярных и 5 последних поисков
```

---

## Роль каждого файла

| Файл | Слой | Задача |
|---|---|---|
| `run.py` | Запуск | Единственная точка входа всего проекта, `debug` читается из `FLASK_DEBUG` (по умолчанию `False`) |
| `local_settings.py` | Конфигурация | MySQL (Sakila read/write) и MongoDB credentials, SECRET_KEY — не в Git |
| `__init__.py` | Flask | Создаёт `app`, настраивает `sys.path` на корень проекта, грузит `.env`, подключает `firecrawl_bp` и `routes` |
| `routes.py` | Controller | Принимает HTTP-запросы, вызывает `_enrich_with_posters()` для подмешивания постеров |
| `mysql_connector.py` | Model / MySQL | SQL-запросы к Sakila, параметризованные (`%s`) |
| `mongo_logger.py` | Model / MongoDB | Запись логов поиска, отказоустойчивый |
| `log_stats.py` | Model / MongoDB | Чтение агрегированной статистики |
| `film_news.py` | Service | Обёртка над `services/firecrawl` — `get_film_news(title)` |
| `movie_images.py` | — | **Устарело, не используется.** Оставлено на диске, не импортируется |
| `base.html` | View | Навигация, Bootstrap 5, общая структура |
| `index.html` | View | Карточки фильмов, форма поиска, жанровые кнопки |
| `gallery.html` | View | Сетка всех AI-постеров, пагинация, кнопка «Обновить постер» |
| `stats.html` | View | Таблицы популярных и последних поисков |

---

## Базы данных

### MySQL — Sakila (чтение)

```
film ──── film_category ──── category
 │               │                │
film_id       film_id         category_id
title         category_id     name (жанр)
release_year
rating
length
```

Хост: `ich-db.edu.itcareerhub.de` · База: `sakila` · Только чтение.

### MongoDB (запись и чтение)

```
База: itch_films_logs
  └── Коллекция: search_logs
        └── Документ:
              _id           ObjectId
              timestamp     DateTime
              search_type   "title" | "genre" | "year"
              search_value  строка запроса
              genre         название жанра или ""
              year_from     год от или ""
              year_to       год до или ""
              results_count число найденных фильмов
```

Хост: `localhost:27017` · Создаётся автоматически при первом поиске.

---

## AI-постеры — архитектура и текущее состояние

### Пайплайн генерации (`services/ai_posters/`)

```
1. prompt_builder.build_prompt(title, genre, description)
       → (prompt, negative_prompt)   — жанр определяет визуальный стиль (auto-mapping)

2. provider.generate(prompt, ...) → bytes (WebP)
       OpenAIProvider  — реальный вызов OpenAI Images API (gpt-image-2, quality=low,
                          1024×1536, output_format=webp). Используется только CLI-скриптом
                          scripts/generate_movie_posters.py — платный вызов.
       MockProvider    — рисует однотонный WebP через Pillow, без сети и без затрат.
                          Используется как: (а) fallback для фильмов, заблокированных
                          OpenAI-модерацией, (б) провайдер для /api/poster/regenerate —
                          Flask-эндпоинт жёстко привязан к MockProvider, чтобы кнопка
                          «Обновить постер» в галерее не могла случайно потратить деньги.

3. storage.save(bytes) → filename        (PosterStorage, storage/posters/)
4. repository.save(...) → poster_id      (PosterRepository, таблица movie_posters)
```

### Версионирование постеров

Таблица `movie_posters` **хранит историю, а не текущее состояние**: у одного `film_id`
может быть несколько записей (разные попытки, mock → openai миграция, ручная
регенерация). Ни одна запись не перезаписывается и не удаляется при новой генерации —
`PosterService.generate()` всегда вставляет новую строку.

«Актуальный» постер для фильма — это запись с `MAX(id)` среди `status='completed'`
для этого `film_id` (`PosterRepository.get_latest_by_film_id[s]`). Несколько записей
на один `film_id` — это ожидаемое поведение, а не дублирование данных, требующее чистки.

### Очередь генерации (`movie_generation_queue`)

`GenerationQueue` — таблица `film_id → status (pending/processing/done/failed)`,
используется только CLI-скриптом для батчевой генерации через OpenAI. `failed` никогда
не ретраится автоматически — только явным флагом `--retry-failed`.

### Текущее состояние данных (аудит 2026-08-10)

| Метрика | Значение |
|---|---|
| Фильмов в Sakila | 1001 |
| Постеров через OpenAI | 996 |
| Постеров через MockProvider (fallback) | 5 — заблокированы модерацией OpenAI (SHREK/PINOCCHIO/JEDI, вероятно trademark) |
| Фильмов с отображаемым постером | 1001 / 1001 (100%) |
| Очередь: `done` / `failed` / `pending` | 996 / 5 / 0 |
| Записей в `movie_posters` всего | 2111 (у каждого film_id несколько версий — см. выше) |
| Orphan WebP-файлов на диске (без записи в БД) | 3 — не blocker, не используются приложением, безопасны для очистки при желании |
| DB-записей, указывающих на отсутствующий файл | 0 |

### Firecrawl в ITCH Films

`film_news.py` — тонкая обёртка над `services/firecrawl.FirecrawlClient` (тот же клиент,
что используется в корневом Flask API проекта). `/api/film/news?title=...` вызывает
`client.search(f"{title} film")` и возвращает реальные результаты веб-поиска
(Wikipedia, IMDb, тематические статьи) в модалку «Подробнее» на карточке фильма.
При любой ошибке возвращает пустой список — сайт не падает.

### Галерея и пагинация

`/gallery` показывает все 1001 постер, по 24 на страницу (`PAGE_SIZE = 24` в `routes.py`),
пагинация через `?offset=N`. Каждая карточка имеет кнопку «Обновить постер»
(`/api/poster/regenerate`, MockProvider) — проверено вручную, работает.

### Тесты

`python -m pytest -v` из корня проекта (`pytest.ini`: `testpaths = tests`) —
**162 теста, все passed**, 0 failed, 0 skipped, 0 warnings (проверено 2026-08-10).
Покрывает: `tests/test_generate_posters.py` (CLI-скрипт, очередь, dry-run safety),
`tests/test_openai_provider.py` (маппинг размеров/параметров OpenAI API),
`tests/test_firecrawl_client.py`, `tests/test_routes.py` (корневой Firecrawl API).
Прямых тестов на цветовую палитру `MockProvider` нет — смена палитры не ломает
существующие assertions.

---

## Принципы архитектуры

- **Separation of concerns** — каждый файл отвечает ровно за одну задачу.
- **Fail-safe MongoDB** — недоступность MongoDB не роняет сайт, логирование пропускается тихо.
- **Разделение конфигурации по назначению, не разброс** — MySQL/MongoDB credentials для
  `itch_films` живут только в `itch_films/local_settings.py`; внешние API-ключи
  (`FIRECRAWL_API_KEY`, `OPENAI_API_KEY`) и конфигурация корневого сервиса — только
  в `.env`. Оба файла в `.gitignore`, ни один секрет не должен попадать в Git.
- **Параметризованные SQL-запросы** — защита от SQL-инъекций через `%s`.
- **Strategy pattern для AI-провайдеров** — `PosterService` зависит от абстракции
  `AIImageProvider`, не от конкретного класса; смена `MockProvider` → `OpenAIProvider`
  требует правки одной строки в точке сборки, а не в самом сервисе.
- **Repository pattern** — вся работа с `movie_posters` и очередью идёт через
  `PosterRepository` / `GenerationQueue`, нигде больше нет сырых SQL-запросов к этим таблицам.
- **Версионирование вместо перезаписи** — постеры никогда не удаляются при регенерации,
  всегда добавляется новая запись; «текущая» версия вычисляется через `MAX(id)`.