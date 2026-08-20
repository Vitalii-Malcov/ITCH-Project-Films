"""
scripts/debug/mock_blocked.py
Генерирует mock-постеры для 5 фильмов, навсегда заблокированных
модерацией OpenAI (moderation_blocked).

Контекст: обычная генерация (scripts/generate_movie_posters.py,
provider=OpenAIProvider) отправляет название/описание/жанр фильма в
OpenAI как часть промпта для изображения. Для этих 5 film_id API OpenAI
стабильно отказывает по модерации — скорее всего из-за формулировок в
названии или описании самого фильма в Sakila. Дальше пытаться через
OpenAI бессмысленно (те же деньги, тот же отказ), поэтому здесь для них
используется MockProvider — он рисует одноцветный WebP на основе жанра
без единого обращения к API, только чтобы у карточки фильма на сайте
была хоть какая-то картинка вместо пустого плейсхолдера.

Сохранённая запись получает provider='mock' — этим она отличима от
настоящих OpenAI-постеров везде, где используется movie_posters
(например, в audit_posters.py и count_audit.py), и её всегда можно будет
позже перегенерировать через OpenAI, если модерация когда-нибудь
пропустит эти фильмы (см. openai_poster_exists() в PosterRepository —
mock-записи туда намеренно не попадают).

Запуск из корня проекта:
    python scripts/debug/mock_blocked.py
"""

import os
import sys

# Скрипт лежит в itch_films_OOP/scripts/debug/, поэтому корень проекта —
# на два уровня выше (scripts/debug/ → scripts/ → корень). Нужен для
# import local_settings и import services.ai_posters ниже.
_script_dir = os.path.dirname(os.path.abspath(__file__))
_itch_films = os.path.normpath(os.path.join(_script_dir, '..', '..'))

if _itch_films in sys.path:
    sys.path.remove(_itch_films)
sys.path.insert(0, _itch_films)

# Принудительно UTF-8 на Windows (консоль по умолчанию — cp1252,
# в неё не помещаются русские буквы из print() ниже).
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(_itch_films, '.env'))

import mysql.connector
import local_settings

# services.ai_posters — общий (не веб-специфичный) пакет для генерации
# постеров, тот же самый, что использует scripts/generate_movie_posters.py.
# Здесь берём MockProvider вместо OpenAIProvider — PosterService работает
# с любым провайдером через один и тот же интерфейс (dependency injection),
# поэтому остальной код (сохранение файла, запись в БД) не меняется вообще.
from services.ai_posters import (
    MockProvider, PosterStorage, PosterRepository, PosterService,
)

STORAGE_DIR = os.path.join(_itch_films, 'storage', 'posters')

# 5 film_id, для которых OpenAI стабильно возвращает moderation_blocked —
# список получен вручную по логам предыдущих запусков
# scripts/generate_movie_posters.py, здесь просто зафиксирован как
# константа, чтобы не гадать заново при каждом запуске.
BLOCKED_IDS = [54, 153, 516, 680, 792]

LINE = '=' * 52


def fetch_film(film_id: int) -> dict | None:
    """
    Читает один фильм из Sakila (только для чтения) по film_id.

    LEFT JOIN + GROUP BY + MIN(c.name) — тот же приём, что и в
    FilmRepository.get_film_by_id() (app/repositories/film_repository.py):
    у фильма может быть несколько жанров в film_category, без GROUP BY
    один film_id дал бы несколько строк, а MIN() берёт один (алфавитно
    первый) жанр, чтобы гарантированно вернуть ровно одну запись.

    Возвращает None, если film_id не найден — вызывающий код (main())
    обязан это проверять и пропускать такие film_id.
    """
    conn   = mysql.connector.connect(**local_settings.dbconfig)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT   f.film_id, f.title, f.description,
                 MIN(c.name) AS genre
        FROM     film f
        LEFT JOIN film_category fc ON f.film_id      = fc.film_id
        LEFT JOIN category      c  ON fc.category_id = c.category_id
        WHERE    f.film_id = %s
        GROUP BY f.film_id, f.title, f.description
    """, (film_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def main():
    """
    Генерирует mock-постеры для всех фильмов из BLOCKED_IDS.

    Идёт по списку последовательно (не батчем/параллельно) — фильмов
    всего 5, а MockProvider ничего не вызывает по сети, так что скорость
    здесь не важна; последовательный цикл проще читать и отлаживать.
    Ошибка на одном film_id не должна останавливать обработку остальных —
    поэтому try/except внутри цикла, а не вокруг него целиком.
    """
    print(LINE)
    print("  Генератор mock-постеров — 5 заблокированных модерацией фильмов")
    print("  Провайдер: MockProvider (одноцветный WebP, без API)")
    print(LINE)

    service = PosterService(
        provider   = MockProvider(),
        storage    = PosterStorage(STORAGE_DIR),
        repository = PosterRepository(),
    )

    generated = 0
    for film_id in BLOCKED_IDS:
        film = fetch_film(film_id)
        if not film:
            # Такое возможно, если Sakila на этой машине отличается от
            # той, где список BLOCKED_IDS был составлен изначально
            # (например, локальная тестовая копия базы с другими id).
            print(f"  [ПРОПУСК] film_id={film_id} не найден в Sakila")
            continue

        # В Sakila description иногда пустой. PosterService передаёт этот
        # текст дальше в построение промпта для изображения (см.
        # build_prompt в services/ai_posters/) — пустая строка там дала бы
        # совсем неинформативную картинку. Поэтому если описания нет,
        # собираем минимальное синтетическое из названия и жанра, вместо
        # того чтобы передавать пустоту.
        desc = (film.get('description') or '').strip()
        if not desc:
            desc = f"{film['title']}. A {film.get('genre') or 'Drama'} film."

        print(f"\n  [{film_id}] {film['title']}  (genre: {film.get('genre') or 'N/A'})")
        try:
            poster_id = service.generate(
                film_id     = film['film_id'],
                title       = film['title'],
                genre       = film.get('genre') or '',
                description = desc,
            )
            url = service.get_poster_url(film['film_id'])
            print(f"       poster_id={poster_id}  url={url}")
            generated += 1
        except Exception as exc:
            # MockProvider ничего не вызывает по сети, поэтому ошибка тут
            # маловероятна (например, PosterStorage не смог записать файл
            # на диск) — но всё равно ловим и печатаем, а не роняем весь
            # скрипт из-за одного film_id.
            print(f"       [ОШИБКА] {exc}")

    print()
    print(LINE)
    print(f"  Сгенерировано : {generated} / {len(BLOCKED_IDS)}")
    print(f"  Провайдер     : mock (без вызовов OpenAI API, бесплатно)")
    print(LINE)


if __name__ == '__main__':
    main()
