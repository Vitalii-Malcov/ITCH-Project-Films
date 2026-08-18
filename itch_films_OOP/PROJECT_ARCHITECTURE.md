# Project Architecture — ITCH Films Premium (ООП-версия)

**Stack:** Python 3.14 · Flask 3.1.3 · MySQL (Sakila, read-only) · MongoDB 7.0.37 · OpenAI Images API (`gpt-image-2`) · Firecrawl · Bootstrap 5

> Этот проект — самостоятельная копия [`../itch_films/`](../itch_films/),
> переработанная под ООП (см. раздел «ООП-переработка» ниже), независимая
> от `../itch_films_2/` (Firecrawl API-сервис; имя папки по историческим
> причинам, к каталогу фильмов отношения не имеет). Собственный
> `services/firecrawl/` — урезанная копия клиента (`client.py`/`models.py`/
> `exceptions.py`), нужная исключительно для одной фичи: блок «Подробнее»
> на карточке фильма. Это не сетевая зависимость от другого сервиса —
> просто повторно используемый код.

---

## ООП-переработка

Отличия от процедурной версии (`../itch_films/`) — переписан только веб-слой,
данные и БД-доступ; `services/ai_posters/` и `services/firecrawl/` уже были
классами и не менялись.

| Было (функции модуля) | Стало (класс) | Где |
|---|---|---|
| `mysql_connector.py` — 7 функций + 2 `@lru_cache` | `FilmRepository` — методы + кэш в `self._genres_cache`/`self._year_range_cache` | `app/repositories/film_repository.py` |
| `mongo_logger.py` — модульный `_collection` + `_connect()` | `MongoConnection` (общая обёртка) + `SearchLogger` | `app/services/mongo_connection.py`, `app/services/search_logger.py` |
| `log_stats.py` — свой отдельный `_collection` + `_connect()` (дублировал mongo_logger.py) | `SearchStatsRepository`, получает `MongoConnection` через конструктор | `app/services/search_stats.py` |
| `film_news.py` — модульный `_client` + `_get_client()` | `FilmNewsService` — то же состояние, но в `self._client` | `app/services/film_news_service.py` |
| `_enrich_with_posters()` — функция в `routes.py` | `PosterEnricher` | `app/services/poster_enricher.py` |

**Что НЕ переделывалось и почему:**
- `routes.py` остался Flask view-функциями с `@app.route` — это стандартный
  Flask-идиом, а не отступление от ООП: функции внутри вызывают методы
  объектов (`film_repository.search_by_title(...)`) вместо голых функций
  модуля. Полные class-based views (`Flask.views.MethodView`) — тоже
  валидный вариант, но менее типичный для Flask и не был выбран.
- `scripts/generate_movie_posters.py` и его тесты (изначально 79, сейчас 80 —
  см. «Проверено на равнозначность» ниже) — оставлены как есть
  (уже вызывают ООП-классы `PosterService`/`GenerationQueue`/`OpenAIProvider`
  внутри, а сам скрипт — одноразовый CLI-раннер, а не часть веб-приложения).
- `_parse_year()` в `routes.py` — чистая функция валидации без обращения
  к БД/сети; превращать её в класс ради класса не имело смысла.

**Что дополнительно улучшено при переносе (не только "функция → метод"):**
- `mongo_logger.py` и `log_stats.py` дублировали один и тот же код
  подключения к MongoDB (`MongoClient` + `server_info()` + `try/except`)
  — теперь это один класс `MongoConnection`, а `SearchLogger`/
  `SearchStatsRepository` получают готовое подключение через конструктор
  (dependency injection), не занимаясь подключением сами.
- 4 SQL-запроса в `mysql_connector.py` вручную собирали один и тот же
  словарь из 7 колонок — вынесено в `FilmRepository._row_to_movie()`.

**Проверено на равнозначность (на момент ООП-переделки, 2026-08-14):** оба тестовых
прогона (`pytest`, 116 unit + 37 Playwright против живого сервера) проходили так же,
как в `itch_films/` — поведение сайта не изменилось, изменилась только внутренняя
организация кода. С тех пор в `itch_films_OOP` добавлены дополнительные unit-тесты
для исправлений, специфичных для этой копии (fencing-token в очереди генерации,
rate limiter — см. `tests/test_queue_fencing.py`, `tests/test_rate_limiter.py`),
не перенесённых обратно в `itch_films/`: сейчас 129 unit + 37 Playwright.

---

## Структура файлов

```
itch_films_OOP/
├── run.py                   # Точка входа: python itch_films_OOP/run.py (или python run.py из этой папки)
├── local_settings.py        # Настройки подключения (MySQL read/write, MongoDB, SECRET_KEY)
├── requirements.txt         # Production-зависимости
├── requirements-dev.txt     # Dev-зависимости (pytest, playwright)
├── .env                     # OPENAI_API_KEY, FIRECRAWL_API_KEY — НЕ коммитить
├── .env.example
├── pytest.ini                # testpaths=tests, pythonpath=.
├── app/
│   ├── __init__.py          # Создаёт Flask-приложение, настраивает sys.path на
│   │                        # itch_films_OOP/, грузит .env, подключает routes
│   ├── routes.py            # URL-маршруты: /, /search, /gallery, /stats, /api/*
│   │                        # (view-функции вызывают методы объектов ниже)
│   ├── repositories/
│   │   └── film_repository.py    # class FilmRepository — все SQL-запросы к Sakila
│   ├── services/
│   │   ├── mongo_connection.py   # class MongoConnection — общая обёртка подключения
│   │   ├── search_logger.py      # class SearchLogger — запись поисков в MongoDB
│   │   ├── search_stats.py       # class SearchStatsRepository — чтение статистики
│   │   ├── film_news_service.py  # class FilmNewsService — обёртка над FirecrawlClient
│   │   ├── poster_enricher.py    # class PosterEnricher — подмешивание постеров
│   │   └── rate_limiter.py       # class RateLimiter — in-memory rate limit (без внешних зависимостей)
│   ├── static/css/
│   │   └── style.css        # Glassmorphism, dark theme, анимации
│   └── templates/
│       ├── base.html        # Базовый шаблон (навигация, Bootstrap 5)
│       ├── index.html       # Главная страница и результаты поиска
│       ├── gallery.html     # Галерея всех AI-постеров, 24 на страницу
│       └── stats.html       # Страница статистики MongoDB
├── services/
│   ├── ai_posters/          # Пайплайн генерации AI-постеров (см. ниже) — уже классы
│   └── firecrawl/           # Собственная копия Firecrawl-клиента (см. баннер выше) — уже класс
├── scripts/
│   ├── generate_movie_posters.py  # CLI: массовая генерация через OpenAIProvider
│   ├── test_openai_poster.py      # Разовый ручной тест OpenAIProvider
│   └── debug/                     # Диагностические скрипты (не в Git)
├── storage/posters/          # WebP-постеры (не в Git — .gitignore)
├── tests/
│   ├── conftest.py, test_itch_films.py       # Playwright, нужен запущенный сервер
│   ├── test_openai_provider.py               # Unit-тесты OpenAIProvider
│   ├── test_generate_posters.py              # Unit-тесты CLI-скрипта и очереди
│   ├── test_queue_fencing.py                 # Unit-тесты claim_token/fencing в GenerationQueue
│   └── test_rate_limiter.py                  # Unit-тесты RateLimiter
├── docs/                      # Исторические отчёты и прогресс
└── .claude/project_vision.md  # Vision-документ курсового проекта
```

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
```

`services/ai_posters` и `services/firecrawl` становятся импортируемыми благодаря
`sys.path.insert()` в **`app/__init__.py`** — единой точке инициализации, до
импорта любых маршрутов.

---

## Маршруты (`routes.py`)

| Метод | URL | Описание |
|---|---|---|
| GET | `/` | Главная страница, форма поиска |
| GET | `/search` | Поиск по названию/жанру/году; постеры подмешиваются из `movie_posters` |
| GET | `/api/suggest` | JSON-автокомплит, до 5 фильмов |
| GET | `/api/film/news?title=...` | Firecrawl-поиск доп. информации о фильме; `title` ограничен 200 символами, rate limit 10 запросов/мин с IP (429 при превышении) |
| GET | `/gallery` | Галерея всех 1001 постеров, пагинация по 24 |
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
     ├─► film_repository.search_by_title() / .search_by_genre() ──► MySQL (Sakila, read-only)
     │       FilmRepository (app/repositories/film_repository.py)   SELECT film_id, title,
     │                                                              release_year, rating,
     │                                                              length, genre
     │       Возвращает: список словарей
     │
     ├─► poster_enricher.enrich() ──► PosterRepository.get_latest_by_film_ids()
     │       PosterEnricher (app/services/poster_enricher.py) вызывает уже-ООП
     │       PosterRepository — один JOIN-запрос на всю страницу результатов:
     │       SELECT mp.* FROM movie_posters mp
     │       INNER JOIN (SELECT film_id, MAX(id) FROM movie_posters
     │                    WHERE status='completed' GROUP BY film_id) latest
     │       ON mp.id = latest.max_id
     │       Фильмы без записи получают DEFAULT_POSTER (placeholder)
     │
     ├─► search_logger.log_search() ──► MongoDB
     │       SearchLogger (app/services/search_logger.py)
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
SearchLogger.log_search(search_type, search_value, genre,
                        year_from, year_to, results_count)
     │
     ▼
MongoDB  (база: itch_films_logs, коллекция: search_logs)
     │  Документ: { timestamp, search_type, search_value,
     │              genre, year_from, year_to, results_count }
     │
     │                    (позже, при переходе на /stats)
     ▼
SearchStatsRepository
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
| `run.py` | Запуск | Точка входа проекта, `debug` читается из `FLASK_DEBUG` (по умолчанию `False`) |
| `local_settings.py` | Конфигурация | MySQL (Sakila read/write) и MongoDB credentials, SECRET_KEY — не в Git |
| `__init__.py` | Flask | Создаёт `app`, настраивает `sys.path` на `itch_films_OOP/`, грузит `.env`, подключает `routes` |
| `routes.py` | Controller | Принимает HTTP-запросы, вызывает методы объектов `film_repository`/`search_logger`/`search_stats`/`film_news_service`/`poster_enricher` |
| `repositories/film_repository.py` | Model / MySQL | `class FilmRepository` — SQL-запросы к Sakila, параметризованные (`%s`), кэш жанров/годов в `self` |
| `services/mongo_connection.py` | Model / MongoDB | `class MongoConnection` — общее подключение (DI в `SearchLogger`/`SearchStatsRepository`) |
| `services/search_logger.py` | Model / MongoDB | `class SearchLogger` — запись логов поиска, отказоустойчивый |
| `services/search_stats.py` | Model / MongoDB | `class SearchStatsRepository` — чтение агрегированной статистики |
| `services/film_news_service.py` | Service | `class FilmNewsService` — обёртка над `services/firecrawl` |
| `services/poster_enricher.py` | Service | `class PosterEnricher` — подмешивает `image_url` в список фильмов |
| `services/rate_limiter.py` | Service | `class RateLimiter` — in-memory sliding-window лимит запросов по IP, без внешних зависимостей (не шарится между процессами) |
| `base.html` | View | Навигация, Bootstrap 5, общая структура |
| `index.html` | View | Карточки фильмов, форма поиска, жанровые кнопки |
| `gallery.html` | View | Сетка всех AI-постеров, пагинация |
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
                          Используется как fallback для фильмов, заблокированных
                          OpenAI-модерацией, и в тестах.

3. storage.save(bytes) → filename        (PosterStorage, storage/posters/)
4. repository.save(...) → poster_id      (PosterRepository, таблица movie_posters)
```

`PosterStorage.save()` создаёт файл через `open(path, 'xb')` (эксклюзивное создание) с
повтором при коллизии имени — а не `'wb'`, который тихо перезаписал бы файл при гонке
между двумя одновременными генерациями. Если шаг 4 (запись в БД) падает после того, как
файл уже записан на диск, `PosterService.generate()` удаляет этот осиротевший файл, прежде
чем пробросить исключение дальше — чтобы неудачные генерации не копили мусор в
`storage/posters/`.

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

Захват элемента очереди (`mark_processing()`) — атомарный `UPDATE ... WHERE status='pending'`
(а не read-then-write из `get_pending()`+отдельного UPDATE), чтобы два параллельных запуска
скрипта не могли забрать один и тот же элемент и сгенерировать постер дважды. При успешном
захвате `mark_processing()` возвращает `claim_token` — счётчик, увеличивающийся при каждом
захвате строки. `mark_done()`/`mark_failed()` принимают этот token и применяют изменение,
только если он всё ещё совпадает с текущим значением в БД («fencing token» / optimistic
concurrency): если элемент по таймауту (`processing_started_at`, не `created_at`) был сброшен
в `pending` и захвачен заново другим запуском, результат первого (уже неактуального) захвата
не перезапишет статус нового.

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

`FilmNewsService` (`app/services/film_news_service.py`) — тонкая обёртка над собственной
копией `services/firecrawl.FirecrawlClient` внутри `itch_films_OOP/`.
`/api/film/news?title=...` вызывает `client.search(f"{title} film")`
и возвращает реальные результаты веб-поиска (Wikipedia, IMDb, тематические статьи)
в модалку «Подробнее» на карточке фильма. При любой ошибке возвращает пустой список —
сайт не падает.

### Галерея и пагинация

`/gallery` показывает все 1001 постер, по 24 на страницу (`PAGE_SIZE = 24` в `routes.py`),
пагинация через `?offset=N`.

### Тесты

`python -m pytest -v` из `itch_films_OOP/` (`pytest.ini`: `testpaths = tests`) —
129 unit-тестов, полностью замоканы (без реальных БД/API), покрывает:
`tests/test_generate_posters.py` (80, CLI-скрипт, очередь, dry-run safety),
`tests/test_openai_provider.py` (37, маппинг размеров/параметров OpenAI API),
`tests/test_queue_fencing.py` (7, claim_token/fencing в `GenerationQueue`),
`tests/test_rate_limiter.py` (5, `RateLimiter`).
`tests/test_itch_films.py` (37) — Playwright-тесты, требуют предварительно запущенного
сервера (`python run.py` в отдельном терминале), запускаются отдельно и не входят
в CI (`.github/workflows/itch-films-oop-ci.yml` гоняет только unit-тесты).
Прямых тестов на цветовую палитру `MockProvider` нет — смена палитры не ломает
существующие assertions.

---

## Принципы архитектуры

- **Separation of concerns** — каждый файл отвечает ровно за одну задачу.
- **Fail-safe MongoDB** — недоступность MongoDB не роняет сайт, логирование пропускается тихо.
- **Разделение конфигурации по назначению** — MySQL/MongoDB credentials живут только
  в `local_settings.py`; внешние API-ключи (`FIRECRAWL_API_KEY`, `OPENAI_API_KEY`)
  — только в `.env`. Оба файла в `.gitignore`, ни один секрет не должен попадать в Git.
- **Repository / Service слой веб-приложения** — `FilmRepository`, `SearchLogger`,
  `SearchStatsRepository`, `FilmNewsService`, `PosterEnricher`: каждый класс отвечает
  за одну внешнюю систему (MySQL, MongoDB-запись, MongoDB-чтение, Firecrawl, постеры),
  `routes.py` не содержит ни одного прямого обращения к БД.
- **Dependency Injection для MongoDB** — `SearchLogger`/`SearchStatsRepository` получают
  готовый `MongoConnection` через конструктор, а не создают подключение сами — упрощает
  замену на mock-подключение в тестах и убирает дублирование кода подключения.
- **Параметризованные SQL-запросы** — защита от SQL-инъекций через `%s`.
- **Strategy pattern для AI-провайдеров** — `PosterService` зависит от абстракции
  `AIImageProvider`, не от конкретного класса; смена `MockProvider` → `OpenAIProvider`
  требует правки одной строки в точке сборки, а не в самом сервисе.
- **Repository pattern** — вся работа с `movie_posters` и очередью идёт через
  `PosterRepository` / `GenerationQueue`, нигде больше нет сырых SQL-запросов к этим таблицам.
- **Версионирование вместо перезаписи** — постеры никогда не удаляются при регенерации,
  всегда добавляется новая запись; «текущая» версия вычисляется через `MAX(id)`.
- **Optimistic concurrency / fencing token** — захват элемента очереди генерации
  атомарен (условный `UPDATE ... WHERE status='pending'`), а `claim_token` защищает
  от того, что результат устаревшего (перезахваченного по таймауту) захвата
  перезапишет статус нового — см. «Очередь генерации» выше.
- **Атомарная запись файлов** — `PosterStorage.save()` создаёт файл через
  `open(path, 'xb')` (эксклюзивно), а не `'wb'`, чтобы два одновременных сохранения
  не могли перезаписать файл друг друга при коллизии имени.
- **Rate limiting без внешних зависимостей** — `/api/film/news` (платный, без
  аутентификации) защищён простым in-memory `RateLimiter`; для проекта без
  системы логина это осознанный компромисс вместо полноценной авторизации.
