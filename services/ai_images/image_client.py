import os
import struct
import zlib


class MockImageClient:
    """
    Development placeholder — replace with real AI image API later.
    Accepted APIs: DALL-E (OpenAI), Stable Diffusion, Midjourney, etc.
    """

    def generate(self, prompt: str, output_path: str) -> str:
        """
        Write a placeholder PNG to output_path.
        Returns output_path on success.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        _write_placeholder_png(output_path)
        return output_path


def _write_placeholder_png(filepath: str, width: int = 400, height: int = 600) -> None:
    """
    Write a minimal valid PNG without external dependencies.
    Colour: dark blue-grey (#1a1a2e) — matches the ITCH Films dark theme.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack('>I', len(data))
            + body
            + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
        )

    # Each row: filter-byte (0 = None) + RGB pixels
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