# ITCH Films Premium

Курсовой проект — премиальный каталог фильмов на Flask + MySQL (Sakila) + MongoDB,
с AI-генерируемыми постерами (OpenAI Images API).

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
- Flask 3.0.3
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
itch_films/
├── run.py                       # Точка входа
├── local_settings.py            # DB credentials (не в Git)
├── app/                         # Flask-приложение: routes, templates, static
├── services/
│   ├── ai_posters/               # Пайплайн генерации AI-постеров
│   └── firecrawl/                # Собственная копия Firecrawl-клиента
├── scripts/
│   └── generate_movie_posters.py # CLI: массовая генерация постеров через OpenAI
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

`tests/test_itch_films.py` — Playwright, требует запущенного сервера в отдельном
терминале (`python run.py`), не входит в обычный прогон unit-тестов.

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
