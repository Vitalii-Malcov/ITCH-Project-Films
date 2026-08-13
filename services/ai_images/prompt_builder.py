def build_movie_poster_prompt(title: str, genre: str, description: str) -> str:
    """
    Строит английский промпт для генерации AI-изображения.
    Промпт намеренно избегает текста, логотипов и реальных людей.
    """
    parts = [
        "cinematic movie poster",
        "no text",
        "no logos",
        "no real actors",
        f"title: {title}",
    ]
    if genre:
        parts.append(f"genre: {genre}")
    if description:
        # Обрезаем до 200 символов, чтобы промпт оставался сфокусированным
        parts.append(f"theme: {description[:200]}")
    parts.append("dramatic lighting, high quality, film industry style")
    return ", ".join(parts)
