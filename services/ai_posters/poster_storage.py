"""
PosterStorage — file system abstraction for WebP poster files.

Responsibilities:
    - Generate sequential filenames (000001.webp, 000002.webp, ...)
    - Write image bytes to disk
    - Translate filenames to absolute paths and URL paths

What it does NOT do:
    - Know about film_id or any database concept
    - Decide what to generate or when
    - Know about Flask or HTTP

The film_id → filename mapping lives only in the database (PosterRepository).
This separation allows multiple poster versions per film without changing
the storage layer at all.

URL note:
    storage/posters/ is outside Flask's static/ folder by design.
    get_url() returns '/posters/<filename>' — a Flask route added in Stage 7
    will serve these files via send_from_directory.
"""

import os
import logging

from services.ai_posters.exceptions import StorageError

logger = logging.getLogger(__name__)

_EXTENSION = '.webp'
_DIGITS = 6  # 000001.webp … 999999.webp


class PosterStorage:
    """Manages WebP poster files in a dedicated storage directory."""

    def __init__(self, storage_dir: str):
        """
        Args:
            storage_dir: Absolute path to the posters folder.
                         Typically: <project_root>/storage/posters/
        """
        self._dir = storage_dir
        os.makedirs(self._dir, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────

    def save(self, image_bytes: bytes) -> str:
        """
        Write image bytes to a new sequential file.

        Returns:
            The filename, e.g. '000001.webp'.

        Raises:
            StorageError: If the file cannot be written.
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
        logger.info(f"Saved poster: {filename} ({len(image_bytes):,} bytes)")
        return filename

    def get_path(self, filename: str) -> str:
        """Return the absolute path for a given filename."""
        return os.path.join(self._dir, filename)

    def get_url(self, filename: str) -> str:
        """
        Return the URL path Flask will use to serve the file.
        Requires a '/posters/<filename>' route in routes.py (Stage 7).
        """
        return f"/posters/{filename}"

    def file_exists(self, filename: str) -> bool:
        """Return True if the file is present on disk."""
        return os.path.isfile(self.get_path(filename))

    # ── Private helpers ───────────────────────────────────────────────

    def _next_filename(self) -> str:
        """
        Determine the next sequential filename.

        Scans the storage directory for existing *.webp files,
        finds the highest number, and returns max + 1.

        Thread-safety: NOT thread-safe. Sufficient for single-process
        batch generation. For concurrent generators, replace with a
        DB sequence or a file-based lock.
        """
        existing = self._existing_numbers()
        next_num = max(existing, default=0) + 1
        return f"{next_num:0{_DIGITS}d}{_EXTENSION}"

    def _existing_numbers(self) -> list[int]:
        """Return a list of numeric IDs parsed from existing WebP filenames."""
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