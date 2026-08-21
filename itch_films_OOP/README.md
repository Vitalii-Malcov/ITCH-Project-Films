# ITCH Films Premium — OOP-версия

Курсовой проект — премиальный каталог фильмов на Flask + MySQL (Sakila) + MongoDB,
с AI-генерируемыми постерами (OpenAI Images API).

> Это ООП-переработка проекта [`../itch_films/`](../itch_films/) — та же
> функциональность, но веб-слой (данные Sakila, MongoDB-логирование,
> Firecrawl-поиск новостей) переписан из плоских функций-модулей в классы
> (Repository/Service паттерны). `services/ai_posters/` и `services/firecrawl/`
> в обоих проектах уже были классами — не менялись. Подробности и решения
> по объёму переделки — в [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md#ооп-переработка).

## Features

- поиск по названию
- поиск по жанру
- поиск по годам
- autocomplete
- gallery
- pagination
- search statistics
- Firecrawl movie information (блок «Подробнее»)
- AI-generated posters
- MockProvider fallback
- poster regeneration without OpenAI costs

## Tech Stack

- Python 3.14
- Flask 3.1.3
- MySQL / Sakila
- MongoDB
- OpenAI Images API
- Firecrawl (собственная копия клиента)
- Bootstrap 5
- Pytest / Playwright

## Architecture

```
Flask
├── MySQL / Sakila
├── MongoDB
├── Firecrawl (собственная копия клиента)
└── AI Poster Service
    ├── Provider
    ├── Prompt Builder
    ├── Poster Service
    ├── Repository
    ├── Storage
    └── Queue
```

Подробное описание — в [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md).

## Project Structure

```
itch_films_OOP/
├── run.py                       # Точка входа
├── local_settings.py            # DB credentials (не в Git)
├── app/
│   ├── __init__.py               # create_app-фабрика
│   ├── routes.py                 # View-функции Flask — вызывают методы классов ниже
│   ├── repositories/
│   │   └── film_repository.py    # class FilmRepository — вся работа с Sakila (MySQL)
│   ├── services/
│   │   ├── mongo_connection.py   # class MongoConnection — общая обёртка подключения
│   │   ├── search_logger.py      # class SearchLogger — запись поисков в MongoDB
│   │   ├── search_stats.py       # class SearchStatsRepository — чтение статистики
│   │   ├── film_news_service.py  # class FilmNewsService — обёртка над FirecrawlClient
│   │   ├── poster_enricher.py    # class PosterEnricher — подмешивание постеров
│   │   └── rate_limiter.py       # class RateLimiter — простой in-memory rate limit
│   ├── static/, templates/
├── services/                     # УЖЕ были классами — не переделывались
│   ├── ai_posters/                # Пайплайн генерации AI-постеров (PosterService и т.д.)
│   └── firecrawl/                 # Собственная копия Firecrawl-клиента (FirecrawlClient)
├── scripts/
│   └── generate_movie_posters.py # CLI-скрипт — оставлен процедурным (см. README)
├── storage/posters/              # Сгенерированные WebP-постеры (не в Git)
├── tests/                        # pytest / Playwright тесты
├── docs/                         # Session summaries, progress checkpoints
├── PROJECT_ARCHITECTURE.md
├── requirements.txt / requirements-dev.txt
└── pytest.ini
```

## Running the project

```
pip install -r requirements-dev.txt
python run.py
```

Запускается на `http://127.0.0.1:5000`. Требует `local_settings.py` с настройками
MySQL (Sakila) и MongoDB, и `.env` с `OPENAI_API_KEY` / `FIRECRAWL_API_KEY`
(см. `.env.example`) — ни один из файлов не хранится в Git.

Windows: если при старте падает `UnicodeEncodeError` из-за кириллицы в консольном
выводе, запускайте с `PYTHONIOENCODING=utf-8`:

```
set PYTHONIOENCODING=utf-8
python run.py
```

## Tests

```
python -m pytest
```

129 unit-тестов (полностью замоканы, без реальных БД/API) — гоняются в CI
(см. бейдж вверху). `tests/test_itch_films.py` (37 Playwright-тестов) требует
запущенного сервера в отдельном терминале (`python run.py`), не входит в обычный
прогон unit-тестов и не входит в CI.

## AI Posters

Current state (аудит 2026-08-10):

- films: 1001
- OpenAI posters: 996
- Mock fallback: 5
- visible posters: 1001/1001
- queue: done=996, failed=5, pending=0

Таблица `movie_posters` хранит версии, а не единственное текущее состояние: при
регенерации новая запись всегда добавляется, а не заменяет старую. Текущий постер
для фильма выбирается как запись с `MAX(id)` среди записей со статусом `completed`
для этого `film_id`.

## Configuration

Секреты (API-ключи, пароли БД) хранятся только в `.env` и `local_settings.py` —
оба файла в `.gitignore` и не должны попадать в Git.

## Documentation

- [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md)
- [`docs/AI_POSTER_PROGRESS.md`](docs/AI_POSTER_PROGRESS.md)
- [`docs/SESSION_SUMMARY_2026-07-11.md`](docs/SESSION_SUMMARY_2026-07-11.md)
- [`docs/TESTING_REPORT.md`](docs/TESTING_REPORT.md)
- [`docs/VISUAL_AUDIT.md`](docs/VISUAL_AUDIT.md)

## Status

Project status: feature complete / final verification.
