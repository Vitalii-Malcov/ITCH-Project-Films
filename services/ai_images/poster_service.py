import os
import logging

from services.ai_images.prompt_builder import build_movie_poster_prompt
from services.ai_images.image_client import MockImageClient
from services.ai_images import poster_repository

logger = logging.getLogger(__name__)

_client = MockImageClient()

# Absolute path to the generated images folder, derived from this file's location
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
    Generate a poster for the film if one is not already in movie_posters.

    Returns:
        'generated' — new poster created and saved
        'skipped'   — record already existed, nothing to do
        'failed'    — an error occurred
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
        logger.info(f"Poster generated for film_id={film_id}: {title}")
        return 'generated'

    except Exception as e:
        logger.error(f"Poster generation failed for film_id={film_id}: {e}")
        return 'failed'