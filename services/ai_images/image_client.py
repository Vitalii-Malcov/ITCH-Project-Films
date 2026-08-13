import os
import struct
import zlib


class MockImageClient:
    """
    Заглушка для разработки — позже заменить на настоящий API AI-изображений.
    Подходящие API: DALL-E (OpenAI), Stable Diffusion, Midjourney и т.д.
    """

    def generate(self, prompt: str, output_path: str) -> str:
        """
        Записывает placeholder-PNG в output_path.
        При успехе возвращает output_path.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        _write_placeholder_png(output_path)
        return output_path


def _write_placeholder_png(filepath: str, width: int = 400, height: int = 600) -> None:
    """
    Записывает минимально корректный PNG без внешних зависимостей.
    Цвет: тёмный сине-серый (#1a1a2e) — совпадает с тёмной темой ITCH Films.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack('>I', len(data))
            + body
            + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
        )

    # Каждая строка: байт-фильтр (0 = None) + пиксели RGB
    row = b'\x00' + b'\x1a\x1a\x2e' * width
    raw = row * height

    png = (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw))
        + chunk(b'IEND', b'')
    )

    with open(filepath, 'wb') as f:
        f.write(png)
