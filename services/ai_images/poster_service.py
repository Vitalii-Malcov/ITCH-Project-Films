import os
import logging

from services.ai_images.prompt_builder import build_movie_poster_prompt
from services.ai_images.image_client import MockImageClient
from services.ai_images import poster_repository

logger = logging.getLogger(__name__)

_client = MockImageClient()

# Абсолютный путь к папке сгенерированных изображений, вычисленный от расположения этого файла
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
GENERATED_DIR = os.path.join(
    _project_root, 'itch_films', 'app', 'static', 'images', 'generated'
)


def generate_poster_if_missing(
    film_id: int,
    title: str,
    genre: str,
    description: str,
) -> str:
    """
    Генерирует постер для фильма, если он ещё не сохранён в movie_posters.

    Возвращает:
        'generated' — новый постер создан и сохранён
        'skipped'   — запись уже существовала, ничего не делаем
        'failed'    — произошла ошибка
    """
    if poster_repository.poster_record_exists(film_id):
        return 'skipped'

    try:
        prompt = build_movie_poster_prompt(title, genre or '', description or '')
        filename = f"film_{film_id}.png"
        image_path = os.path.join(GENERATED_DIR, filename)
        image_url = f"/static/images/generated/{filename}"

        _client.generate(prompt, image_path)

        poster_repository.save_poster_record(
            film_id=film_id,
            title=title,
            genre=genre,
            description=description,
            prompt=prompt,
            image_path=image_path,
            image_url=image_url,
            status='generated',
        )
        logger.info(f"Постер сгенерирован для film_id={film_id}: {title}")
        return 'generated'

    except Exception as e:
        logger.error(f"Генерация постера не удалась для film_id={film_id}: {e}")
        return 'failed'
