"""
PosterService — оркестрирует полный конвейер генерации постера.

Конвейер для одного фильма:
    1. Построить (prompt, negative_prompt) через prompt_builder
    2. Замерить время начала
    3. Сгенерировать байты изображения через provider.generate()
    4. Замерить generation_time
    5. Сохранить WebP-файл через storage.save()  → filename
    6. Сохранить запись в БД через repository.save() → poster_id
    7. Вернуть poster_id

Внедрение зависимостей (Dependency Injection):
    PosterService получает provider, storage и repository как аргументы
    конструктора — никогда не создаёт их сам. Это следует принципу
    инверсии зависимостей: сервис зависит от абстракций
    (AIImageProvider, PosterStorage, PosterRepository), а не от конкретных
    классов. Переключение с MockProvider на OpenAIProvider требует
    изменения одной строки в вызывающем скрипте, а не в этом файле.

Чего PosterService НЕ делает:
    - Не проверяет, существует ли уже постер (ответственность вызывающего кода).
    - Не управляет очередью генерации (ответственность GenerationQueue).
    - Не знает про Flask или HTTP.
"""

import time
import logging

from services.ai_posters.providers.base import AIImageProvider
from services.ai_posters.poster_storage import PosterStorage
from services.ai_posters.poster_repository import PosterRepository
from services.ai_posters.prompt_builder import build_prompt
from services.ai_posters.exceptions import PosterError

logger = logging.getLogger(__name__)

# Размеры постера по умолчанию — портретная ориентация, типичная для постеров фильмов
DEFAULT_WIDTH  = 640
DEFAULT_HEIGHT = 960


class PosterService:
    """Оркестрирует построение промпта, генерацию изображения и сохранение."""

    def __init__(
        self,
        provider: AIImageProvider,
        storage: PosterStorage,
        repository: PosterRepository,
    ) -> None:
        """
        Аргументы:
            provider:   Бэкенд генерации AI-изображений (MockProvider, OpenAIProvider…)
            storage:    Файловая абстракция для WebP-файлов.
            repository: Абстракция базы данных для таблицы movie_posters.
        """
        self._provider   = provider
        self._storage    = storage
        self._repository = repository

    # ── Публичный API ────────────────────────────────────────────────────

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
        Генерирует постер для одного фильма и сохраняет его.

        Вызывающий код (скрипт) отвечает за проверку poster_exists()
        перед вызовом этого метода. PosterService всегда генерирует —
        это позволяет намеренную регенерацию без специальных флагов.

        Аргументы:
            film_id:     ID фильма из Sakila.
            title:       Название фильма.
            genre:       Жанр фильма (используется для авто-выбора стиля).
            description: Описание фильма (используется в промпте как визуальная тема).
            style:       Визуальный стиль. 'auto' определяет по жанру.
            width:       Ширина выходного изображения в пикселях.
            height:      Высота выходного изображения в пикселях.
            seed:        Необязательный seed для воспроизводимых результатов.

        Возвращает:
            poster_id — автоматически сгенерированный ID новой строки movie_posters.

        Исключения:
            ProviderError: если AI-провайдер упал.
            StorageError:  если файл не удалось записать.
            RepositoryError: если запись в БД не удалось сохранить.
        """
        logger.info(f"Генерация постера для film_id={film_id}: {title}")

        # 1. Построить промпт
        prompt, negative_prompt = build_prompt(
            title=title,
            genre=genre,
            description=description,
            style=style,
        )
        logger.debug(f"Промпт ({len(prompt)} символов): {prompt[:120]}...")

        # 2 и 3. Сгенерировать изображение, замерить прошедшее время
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
            f"Генерация завершена: {len(image_bytes):,} байт "
            f"за {generation_time}с ({self._provider.provider_name()})"
        )

        # 4. Сохранить WebP-файл
        filename   = self._storage.save(image_bytes)
        image_path = self._storage.get_path(filename)

        # 5. Сохранить запись в БД
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
            f"Постер сохранён: poster_id={poster_id} "
            f"film_id={film_id} file={filename}"
        )
        return poster_id

    def get_poster_url(self, film_id: int) -> str | None:
        """
        Возвращает URL последнего завершённого постера для фильма.
        Возвращает None, если постера ещё нет.

        Удобная обёртка вокруг PosterRepository.get_latest_by_film_id(),
        чтобы вызывающему коду не нужно было импортировать PosterRepository напрямую.
        """
        try:
            record = self._repository.get_latest_by_film_id(film_id)
            return record['image_url'] if record else None
        except PosterError as exc:
            logger.warning(f"get_poster_url failed for film_id={film_id}: {exc}")
            return None
