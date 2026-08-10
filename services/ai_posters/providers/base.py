"""
Abstract base class for AI image generation providers.

Design: Strategy Pattern
    PosterService depends on AIImageProvider, not on any concrete class.
    Swapping MockProvider → OpenAIProvider requires one line change at the
    composition root (poster_service.py or the generation script).
    Nothing else in the codebase needs to know which provider is active.
"""

from abc import ABC, abstractmethod


class AIImageProvider(ABC):
    """Interface that every AI image provider must implement."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 640,
        height: int = 960,
        seed: int | None = None,
        style: str = "",
    ) -> bytes:
        """
        Generate an image and return its raw bytes (WebP preferred).

        Args:
            prompt:          Main generation prompt.
            negative_prompt: What to avoid in the image.
            width:           Image width in pixels.
            height:          Image height in pixels.
            seed:            Optional seed for reproducible results.
            style:           Style hint, e.g. 'netflix', 'anime', 'vintage'.

        Returns:
            Raw image bytes ready to be written to disk.

        Raises:
            ProviderError: If the provider fails or returns an error.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """
        Return True if the provider is reachable and ready to generate.
        Used by scripts to verify connectivity before starting a batch run.
        """

    @abstractmethod
    def provider_name(self) -> str:
        """
        Return a short provider identifier stored in the database.
        Examples: 'openai', 'mock', 'stability', 'google'.
        """

    @abstractmethod
    def model_name(self) -> str:
        """
        Return the specific model name stored in the database.
        Examples: 'dall-e-3', 'mock-v1', 'stable-diffusion-xl'.
        """