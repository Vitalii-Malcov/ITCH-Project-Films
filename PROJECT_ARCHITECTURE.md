# Project Architecture — IT Career Hub 2

> **Документ содержит два раздела:**
> 1. **IT Career Hub 2** (текущий проект, корень репозитория) — Flask API + Firecrawl + MongoDB.
> 2. **ITCH Films Premium** (субпроект `itch_films/`) — каталог фильмов Flask + MySQL + MongoDB.
> Раздел ITCH Films сохранён как исторический архив и не отражает текущую точку входа проекта.

---

## IT Career Hub 2 — Текущая архитектура

**Stack:** Python 3.11+ · Flask 3.1 · MongoDB 7 · firecrawl-py 4.31 · pytest 9.1
**Точка входа:** `python run.py` (или `flask run`)
**Режим отладки:** управляется через `FLASK_DEBUG=true` в `.env`

### Структура файлов

```
D:\Project_IT_Career_Hub_2\
├── run.py                       # Точка входа. debug читается из FLASK_DEBUG env var
├── pytest.ini                   # Конфигурация pytest (testpaths=tests)
├── requirements.txt             # Production зависимости
├── requirements-dev.txt         # Dev зависимости (pytest)
├── .env                         # Секреты — НЕ коммитить
├── .env.example                 # Пример переменных окружения
├── app/
│   ├── __init__.py              # create_app() — регистрирует blueprints
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
│   ├── conftest.py              # Shared fixtures: app, client
│   ├── test_routes.py           # Тесты Flask маршрутов (MongoDB и Firecrawl замокированы)
│   └── test_firecrawl_client.py # Unit-тесты FirecrawlClient (V1FirecrawlApp замокирован)
└── archive/
    └── firecrawl_service_legacy.md  # Исторический пример первой реализации
```

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

## ITCH Films Premium — Архив субпроекта (`itch_films/`)

> Раздел ниже описывает субпроект в папке `itch_films/`. Его точка входа — `itch_films/run.py`, не корневой `run.py`. Документ сохранён без изменений как исторический архив.

---

# Project Architecture — ITCH Films Premium

**Stack:** Python 3.14 · Flask 3.0.3 · MySQL (Sakila) · MongoDB 7.0.37 · Bootstrap 5

---

## Структура файлов

```
itch_films/
├── run.py                   # Точка входа — запускает Flask-сервер
├── local_settings.py        # Настройки подключения (MySQL, MongoDB, SECRET_KEY)
├── requirements.txt         # Зависимости: Flask, mysql-connector-python, pymongo
└── app/
    ├── __init__.py          # Создаёт Flask-приложение, подключает routes
    ├── routes.py            # URL-маршруты: /, /search, /stats
    ├── mysql_connector.py   # Все SQL-запросы к Sakila
    ├── mongo_logger.py      # Запись поисков в MongoDB
    ├── log_stats.py         # Чтение статистики из MongoDB
    ├── movie_images.py      # Система постеров: FILM_IMAGES, GENRE_IMAGES, формула
    ├── static/css/
    │   └── style.css        # Glassmorphism, dark theme, анимации
    └── templates/
        ├── base.html        # Базовый шаблон (навигация, Bootstrap 5)
        ├── index.html       # Главная страница и результаты поиска
        └── stats.html       # Страница статистики MongoDB
```

---

## Поток 1 — Поиск и отображение фильмов

```
Пользователь
     │  GET /search?q=alien  или  GET /search?genre=Action
     ▼
routes.py  — читает параметры запроса (q, genre)
     │
     ├─► mysql_connector.py ──► MySQL (Sakila DB)
     │       search_movies_by_title()          SELECT film_id, title,
     │       search_movies_by_genre()          release_year, rating,
     │                                         length, genre
     │       Возвращает: список словарей
     │
     ├─► movie_images.py ──► get_movie_image(film_id, genre)
     │       Шаг 1: IMAGE_OVERRIDES[film_id]   (5 ручных исправлений)
     │       Шаг 2: FILM_IMAGES[film_id]       (55 visual keyword URL)
     │       Шаг 3: GENRE_IMAGES[жанр][film_id % 20]  (формула)
     │       Возвращает: URL картинки с Unsplash
     │
     ├─► Collision Resolver (routes.py, в цикле по результатам)
     │       used_images = set()  — отслеживает уже назначенные URL
     │       Если URL уже в set → перебрать (base_idx + offset) % 20
     │       Взять первый свободный слот в GENRE_IMAGES[жанр]
     │       Гарантия: первые 20 фильмов жанра в выдаче — уникальны
     │
     ├─► mongo_logger.py ──► MongoDB
     │       log_search(type, value, genre, results_count)
     │       Записывает документ в коллекцию search_logs
     │
     ▼
HTML Templates (index.html + base.html)
     │  Jinja2: render_template("index.html", movies=..., genres=...)
     ▼
Пользователь видит карточки фильмов с постерами
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
| `run.py` | Запуск | Точка входа, `app.run(debug=True)` |
| `local_settings.py` | Конфигурация | Хранит все credentials, единственное место |
| `__init__.py` | Flask | Создаёт `app`, подключает `routes` |
| `routes.py` | Controller | Принимает HTTP-запросы, вызывает другие модули; Collision Resolver в `/search` |
| `mysql_connector.py` | Model / MySQL | SQL-запросы к Sakila, параметризованные (`%s`) |
| `mongo_logger.py` | Model / MongoDB | Запись логов поиска, отказоустойчивый |
| `log_stats.py` | Model / MongoDB | Чтение агрегированной статистики |
| `movie_images.py` | Service | Выбор постера по трёхшаговой логике |
| `base.html` | View | Навигация, Bootstrap 5, общая структура |
| `index.html` | View | Карточки фильмов, форма поиска, жанровые кнопки |
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

## Система постеров — movie_images.py

```
320 URL в GENRE_IMAGES  (16 жанров × 20 URL, все уникальные)
 55 URL в FILM_IMAGES   (visual keyword по названию фильма)
  5 URL в IMAGE_OVERRIDES (ручные исправления конфликтов)
  1 URL DEFAULT_IMAGE    (заглушка при неизвестном жанре)

Формула для film_id без индивидуального постера:
  index = film_id % 20
  url   = GENRE_IMAGES[жанр][index]

Жанр берётся из MySQL (поле genre в результате запроса),
что обеспечивает поддержку всех film_id от 1 до 1000.

Коллизии формулы (два film_id с одинаковым остатком % 20 в одной выдаче)
устраняются Collision Resolver в routes.py — см. раздел ниже.
```

---

## Collision Resolver — routes.py

Resolver работает на уровне одного HTTP-запроса, не меняя `movie_images.py`.

```
Шаг                  Где              Что происходит
────────────────────────────────────────────────────────────────
get_movie_image()    movie_images.py  Возвращает URL по 3-шаговой логике
Resolver             routes.py        Проверяет URL через used_images (set)
  └─ нет коллизии                    → назначить, добавить в set
  └─ коллизия                        → перебрать offset 1..19:
                                         candidate = GENRE_IMAGES[жанр][(base+off) % 20]
                                         если не в set → взять, выйти
                                         если все 20 заняты → fallback (исходный URL)
```

**Гарантии:**

| Ситуация | Поведение |
|---|---|
| ≤ 20 фильмов одного жанра в выдаче | 100% уникальные изображения |
| > 20 фильмов одного жанра | первые 20 уникальны, остальные — fallback |
| Фильмы из FILM_IMAGES / IMAGE_OVERRIDES | добавляются в `used_images`, коллизий не создают |
| Жанр неизвестен (genre=None) | `GENRE_IMAGES.get(None, [])` → `[]` → `n=0` → только fallback |

**Изменения в коде:**

```python
# app/routes.py — строка 14 (импорт)
from app.movie_images import get_movie_image, DEFAULT_IMAGE, GENRE_IMAGES

# app/routes.py — строки 69–94 (цикл присвоения постеров)
used_images = set()
for movie in movies:
    url = get_movie_image(movie["film_id"], movie.get("genre"))
    if url not in used_images:
        movie["image_url"] = url
        used_images.add(url)
    else:
        genre_list = GENRE_IMAGES.get(movie.get("genre"), [])
        n = len(genre_list)
        base_idx = movie["film_id"] % n if n else 0
        alt_url = url
        for offset in range(1, n):
            candidate = genre_list[(base_idx + offset) % n]
            if candidate not in used_images:
                alt_url = candidate
                break
        movie["image_url"] = alt_url
        used_images.add(alt_url)
```

---

## Принципы архитектуры

- **Separation of concerns** — каждый файл отвечает ровно за одну задачу.
- **Fail-safe MongoDB** — недоступность MongoDB не роняет сайт, логирование пропускается тихо.
- **Единое место конфигурации** — все credentials только в `local_settings.py`.
- **Параметризованные SQL-запросы** — защита от SQL-инъекций через `%s`.
- **Единственное место хранения URL** — все изображения только в `movie_images.py`, никогда в HTML.