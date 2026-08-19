"""
PosterStorage — файловая абстракция для WebP-файлов постеров.

Обязанности:
    - Генерировать последовательные имена файлов (000001.webp, 000002.webp, ...)
    - Записывать байты изображения на диск
    - Преобразовывать имена файлов в абсолютные пути и URL-пути

Чего НЕ делает:
    - Не знает про film_id или любую концепцию базы данных
    - Не решает, что и когда генерировать
    - Не знает про Flask или HTTP

Связь film_id → filename живёт только в базе данных (PosterRepository).
Такое разделение позволяет хранить несколько версий постера на фильм,
вообще не меняя слой хранения.

Заметка про URL:
    storage/posters/ намеренно находится вне папки static/ Flask.
    get_url() возвращает '/posters/<filename>' — маршрут Flask, добавленный
    на Этапе 7, отдаёт эти файлы через send_from_directory.
"""

import os
import logging

from services.ai_posters.exceptions import StorageError

logger = logging.getLogger(__name__)

_EXTENSION = '.webp'
_DIGITS = 6  # 000001.webp … 999999.webp


class PosterStorage:
    """Управляет WebP-файлами постеров в выделенной директории хранения."""

    def __init__(self, storage_dir: str):
        """
        Аргументы:
            storage_dir: Абсолютный путь к папке с постерами.
                         Обычно: <корень_проекта>/storage/posters/
        """
        self._dir = storage_dir
        os.makedirs(self._dir, exist_ok=True)

    # ── Публичный API ────────────────────────────────────────────────────

    def save(self, image_bytes: bytes) -> str:
        """
        Записывает байты изображения в новый последовательный файл.

        Возвращает:
            Имя файла, например '000001.webp'.

        Исключения:
            StorageError: если файл не удалось записать.
        """
        filename = self._next_filename()
        path = self.get_path(filename)
        try:
            with open(path, 'wb') as fh:
                fh.write(image_bytes)
        except OSError as exc:
            raise StorageError(
                f"Could not write poster file: {path}",
                details=str(exc),
            ) from exc
        logger.info(f"Сохранён постер: {filename} ({len(image_bytes):,} байт)")
        return filename

    def get_path(self, filename: str) -> str:
        """Возвращает абсолютный путь для заданного имени файла."""
        return os.path.join(self._dir, filename)

    def get_url(self, filename: str) -> str:
        """
        Возвращает URL-путь, по которому Flask отдаёт файл.
        Требует маршрут '/posters/<filename>' в routes.py (Этап 7).
        """
        return f"/posters/{filename}"

    def file_exists(self, filename: str) -> bool:
        """Возвращает True, если файл присутствует на диске."""
        return os.path.isfile(self.get_path(filename))

    # ── Приватные вспомогательные методы ───────────────────────────────────────

    def _next_filename(self) -> str:
        """
        Определяет следующее по порядку имя файла.

        Сканирует директорию хранения на предмет существующих *.webp файлов,
        находит наибольший номер и возвращает max + 1.

        Потокобезопасность: НЕ потокобезопасно. Достаточно для однопроцессной
        пакетной генерации. Для параллельных генераторов заменить на
        последовательность из БД или файловую блокировку.
        """
        existing = self._existing_numbers()
        next_num = max(existing, default=0) + 1
        return f"{next_num:0{_DIGITS}d}{_EXTENSION}"

    def _existing_numbers(self) -> list[int]:
        """Возвращает список числовых ID, разобранных из существующих имён WebP-файлов."""
        numbers = []
        try:
            for name in os.listdir(self._dir):
                if name.endswith(_EXTENSION):
                    stem = name[: -len(_EXTENSION)]
                    if stem.isdigit():
                        numbers.append(int(stem))
        except OSError as exc:
            raise StorageError(
                f"Cannot read storage directory: {self._dir}",
                details=str(exc),
            ) from exc
        return numbers