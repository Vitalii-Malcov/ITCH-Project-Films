# Firecrawl API Service

Самостоятельный Flask-сервис для скрейпинга, краулинга и веб-поиска через Firecrawl,
с сохранением результатов в MongoDB.

> Каталог фильмов ITCH Films Premium — отдельный независимый проект в папке
> [`../itch_films/`](../itch_films/) (свой `run.py`, свои зависимости, своя
> документация). Он использует свою собственную копию Firecrawl-клиента для
> одной фичи и не зависит от этого сервиса как от процесса.

## Features

- POST `/api/scrape` — скрейп одной страницы
- POST `/api/crawl` — обход сайта по ссылкам
- POST `/api/search` — веб-поиск
- GET `/api/history/<collection>` — история результатов из MongoDB

## Tech Stack

- Python 3.11+
- Flask 3.1
- MongoDB 7
- firecrawl-py 4.31
- pytest 9.1

## Project Structure

```
Project_IT_Career_Hub_2/
├── itch_films/                   # Другой, независимый проект (см. его README)
└── itch_films_2/                 # Этот проект (Firecrawl API-сервис)
    ├── run.py                    # Точка входа
    ├── app/                      # Flask-приложение (routes/firecrawl.py)
    ├── services/
    │   ├── firecrawl/              # Клиент Firecrawl API
    │   └── mongo/                  # Клиент MongoDB
    ├── scripts/
    │   └── check_firecrawl.py      # Ручная проверка (не pytest)
    ├── tests/                     # pytest-тесты
    ├── archive/                   # Исторические заметки
    ├── PROJECT_ARCHITECTURE.md
    ├── requirements.txt / requirements-dev.txt
    └── pytest.ini
```

## Running

```
cd itch_films_2
pip install -r requirements-dev.txt
python run.py
```

Запускается на `http://127.0.0.1:5000`. Требует `.env` (внутри `itch_films_2/`)
с `FIRECRAWL_API_KEY` (см. `.env.example`).

## Tests

Из папки `itch_films_2/`:

```
python -m pytest
```

## Configuration

Секреты (API-ключи) хранятся только в `.env` — файл в `.gitignore`, не коммитится.

## Documentation

- [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md)
