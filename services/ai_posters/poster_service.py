"""
PosterService — orchestrates the full poster generation pipeline.

Pipeline for one film:
    1. Build (prompt, negative_prompt) via prompt_builder
    2. Measure start time
    3. Generate image bytes via provider.generate()
    4. Measure generation_time
    5. Save WebP file via storage.save()  → filename
    6. Save DB record via repository.save() → poster_id
    7. Return poster_id

Dependency Injection:
    PosterService receives provider, storage, and repository as constructor
    arguments — it never creates them internally. This follows the
    Dependency Inversion principle: the service depends on abstractions
    (AIImageProvider, PosterStorage, PosterRepository), not on concrete
    classes. Switching from MockProvider to OpenAIProvider requires
    changing one line in the calling script, not this file.

What PosterService does NOT do:
    - Check whether a poster already exists (caller's responsibility).
    - Manage the generation queue (GenerationQueue's responsibility).
    - Know about Flask or HTTP.
"""

import time
import logging

from services.ai_posters.providers.base import AIImageProvider
from services.ai_posters.poster_storage import PosterStorage
from services.ai_posters.poster_repository import PosterRepository
from services.ai_posters.prompt_builder import build_prompt
from services.ai_posters.exceptions import PosterError

logger = logging.getLogger(__name__)

# Default poster dimensions — portrait aspect ratio, typical for film posters
DEFAULT_WIDTH  = 640
DEFAULT_HEIGHT = 960


class PosterService:
    """Orchestrates prompt building, image generation, and persistence."""

    def __init__(
        self,
        provider: AIImageProvider,
        storage: PosterStorage,
        repository: PosterRepository,
    ) -> None:
        """
        Args:
            provider:   AI image generation backend (MockProvider, OpenAIProvider…)
            storage:    File system abstraction for WebP files.
            repository: Database abstraction for movie_posters table.
        """
        self._provider   = provider
        self._storage    = storage
        self._repository = repository

    # ── Public API ────────────────────────────────────────────────────

    def generate(
        self,
        film_id: int,
        title: str,
        genre: str,
        description: str,
        style: str = 'auto',
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        seed: int | None = None,
    ) -> int:
        """
        Generate a poster for one film and persist it.

        The caller (script) is responsible for checking poster_exists()
        before calling this method. PosterService always generates —
        this allows intentional re-generation without special flags.

        Args:
            film_id:     Sakila film ID.
            title:       Film title.
            genre:       Film genre (used for auto style selection).
            description: Film description (used in prompt as visual theme).
            style:       Visual style. 'auto' detects from genre.
            width:       Output image width in pixels.
            height:      Output image height in pixels.
            seed:        Optional seed for reproducible results.

        Returns:
            poster_id — the auto-generated ID of the new movie_posters row.

        Raises:
            ProviderError: If the AI provider fails.
            StorageError:  If the file cannot be written.
            RepositoryError: If the DB record cannot be saved.
        """
        logger.info(f"Generating poster for film_id={film_id}: {title}")

        # 1. Build prompt
        prompt, negative_prompt = build_prompt(
            title=title,
            genre=genre,
            description=description,
            style=style,
        )
        logger.debug(f"Prompt ({len(prompt)} chars): {prompt[:120]}...")

        # 2 & 3. Generate image, measure elapsed time
        start = time.monotonic()
        image_bytes = self._provider.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            seed=seed,
            style=style,
        )
        generation_time = round(time.monotonic() - start, 3)
        logger.info(
            f"Generation complete: {len(image_bytes):,} bytes "
            f"in {generation_time}s ({self._provider.provider_name()})"
        )

        # 4. Save WebP file
        filename   = self._storage.save(image_bytes)
        image_path = self._storage.get_path(filename)

        # 5. Save DB record
        poster_id = self._repository.save(
            film_id=film_id,
            provider=self._provider.provider_name(),
            model=self._provider.model_name(),
            prompt=prompt,
            negative_prompt=negative_prompt,
            style=style if style != 'auto' else f"auto:{genre.lower()}",
            seed=seed,
            width=width,
            height=height,
            image_path=image_path,
            status='completed',
            generation_time=generation_time,
        )

        logger.info(
            f"Poster saved: poster_id={poster_id} "
            f"film_id={film_id} file={filename}"
        )
        return poster_id

    def get_poster_url(self, film_id: int) -> str | None:
        """
        Return the URL of the latest completed poster for a film.
        Returns None if no poster exists yet.

        Convenience wrapper around PosterRepository.get_latest_by_film_id()
        so callers do not need to import PosterRepository directly.
        """
        try:
            record = self._repository.get_latest_by_film_id(film_id)
            return record['image_url'] if record else None
        except PosterError as exc:
            logger.warning(f"get_poster_url failed for film_id={film_id}: {exc}")
            return None