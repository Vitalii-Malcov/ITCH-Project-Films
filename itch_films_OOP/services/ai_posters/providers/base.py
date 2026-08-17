"""
Абстрактный базовый класс для провайдеров генерации AI-изображений.

Паттерн проектирования: Strategy
    PosterService зависит от AIImageProvider, а не от конкретного класса.
    Замена MockProvider → OpenAIProvider требует изменения одной строки в
    точке сборки (poster_service.py или скрипте генерации).
    Больше нигде в кодовой базе не нужно знать, какой провайдер активен.
"""

from abc import ABC, abstractmethod


class AIImageProvider(ABC):
    """Интерфейс, который должен реализовать каждый AI-провайдер изображений."""

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
        Генерирует изображение и возвращает его сырые байты (предпочтительно WebP).

        Аргументы:
            prompt:          Основной промпт генерации.
            negative_prompt: Чего избегать на изображении.
            width:           Ширина изображения в пикселях.
            height:          Высота изображения в пикселях.
            seed:            Необязательный seed для воспроизводимых результатов.
            style:           Подсказка стиля, например 'netflix', 'anime', 'vintage'.

        Возвращает:
            Сырые байты изображения, готовые к записи на диск.

        Исключения:
            ProviderError: если провайдер упал или вернул ошибку.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """
        Возвращает True, если провайдер доступен и готов генерировать.
        Используется скриптами для проверки связи перед началом пакетного запуска.
        """

    @abstractmethod
    def provider_name(self) -> str:
        """
        Возвращает короткий идентификатор провайдера, хранимый в базе данных.
        Примеры: 'openai', 'mock', 'stability', 'google'.
        """

    @abstractmethod
    def model_name(self) -> str:
        """
        Возвращает конкретное название модели, хранимое в базе данных.
        Примеры: 'dall-e-3', 'mock-v1', 'stable-diffusion-xl'.
        """