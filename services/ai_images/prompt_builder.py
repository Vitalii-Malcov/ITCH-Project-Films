def build_movie_poster_prompt(title: str, genre: str, description: str) -> str:
    """
    Build an English prompt for AI image generation.
    The prompt intentionally avoids text, logos, and real people.
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
        # Trim to 200 chars to keep the prompt focused
        parts.append(f"theme: {description[:200]}")
    parts.append("dramatic lighting, high quality, film industry style")
    return ", ".join(parts)