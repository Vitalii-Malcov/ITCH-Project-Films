# IT Career Hub / ITCH Films Premium

## About

Flask-проект каталога фильмов на базе MySQL Sakila, с MongoDB для статистики поисков,
Firecrawl для дополнительной информации о фильмах и AI-генерируемыми постерами
(OpenAI Images API).

## Features

- поиск по названию
- поиск по жанру
- поиск по годам
- autocomplete
- gallery
- pagination
- search statistics
- Firecrawl movie information
- AI-generated posters
- MockProvider fallback
- poster regeneration without OpenAI costs

## Tech Stack

- Python 3.14
- Flask 3
- MySQL / Sakila
- MongoDB
- OpenAI Images API
- Firecrawl
- Bootstrap
- Pytest

## Architecture

```
Flask
├── MySQL / Sakila
├── MongoDB
├── Firecrawl
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
IT_Career_Hub_2/
├── run.py                       # Точка входа корневого Firecrawl API
├── app/                         # Root Flask API (routes/firecrawl.py)
├── services/
│   ├── firecrawl/                # Клиент Firecrawl API
│   ├── mongo/                    # Клиент MongoDB
│   └── ai_posters/               # Пайплайн генерации AI-постеров
├── scripts/
│   └── generate_movie_posters.py # CLI: массовая генерация постеров через OpenAI
├── storage/posters/              # Сгенерированные WebP-постеры (не в Git)
├── tests/                        # pytest-тесты
├── docs/                         # Session summaries, progress checkpoints
├── itch_films/                   # ITCH Films Premium — основной пользовательский сайт
│   ├── run.py                    # Точка входа сайта
│   ├── local_settings.py         # DB credentials (не в Git)
│   └── app/                      # Flask-приложение: routes, templates, static
├── PROJECT_ARCHITECTURE.md
├── requirements.txt / requirements-dev.txt
└── pytest.ini
```

## Running the project

Установка зависимостей (из корня проекта):

```
pip install -r requirements-dev.txt
```

В репозитории два независимых Flask-приложения — не путайте точки входа.

### ITCH Films Premium — основной пользовательский сайт

```
cd itch_films
python run.py
```

Запускается на `http://127.0.0.1:5000`. Требует `itch_films/local_settings.py`
с настройками MySQL (Sakila) и MongoDB — файл не хранится в Git.

Windows: если при старте падает `UnicodeEncodeError` из-за кириллицы в консольном
выводе, запускайте с `PYTHONIOENCODING=utf-8`:

```
set PYTHONIOENCODING=utf-8
python run.py
```

### Root Firecrawl API — отдельное приложение

```
python run.py
```

(из корня проекта). Это самостоятельный Flask API (`/api/scrape`, `/api/crawl`,
`/api/search`, `/api/history/<collection>`), не связанный с сайтом ITCH Films —
не путайте его с `itch_films/run.py`. Режим отладки управляется `FLASK_DEBUG` в `.env`.

## Tests

```
python -m pytest
```

Current result:

```
162 passed
0 failed
0 skipped
0 warnings
```

## AI Posters

Current state:

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

Секреты (API-ключи, пароли БД) хранятся только в `.env` (корень проекта) и
`itch_films/local_settings.py`. Оба файла в `.gitignore` и не должны попадать в Git.

## Documentation

- [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md)
- [`docs/AI_POSTER_PROGRESS.md`](docs/AI_POSTER_PROGRESS.md)
- [`docs/SESSION_SUMMARY_2026-07-11.md`](docs/SESSION_SUMMARY_2026-07-11.md)

## Status

Project status: feature complete / final verification.