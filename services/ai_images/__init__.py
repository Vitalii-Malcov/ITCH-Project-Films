from services.ai_images.poster_service import generate_poster_if_missing
from services.ai_images.poster_repository import (
    create_movie_posters_table,
    get_poster_by_film_id,
    save_poster_record,
    poster_record_exists,
    get_poster_urls_by_ids,
)