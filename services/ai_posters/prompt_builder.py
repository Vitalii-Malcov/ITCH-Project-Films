"""
prompt_builder — pure functions for AI image prompt construction.

Design decisions:
    - Pure functions: no state, no side effects, no classes.
      Same inputs always produce the same outputs. Easy to test.
    - English only: all major AI image models are trained on English text.
      Non-English prompts produce lower-quality results.
    - Sakila descriptions are formulaic but useful:
        "A [adj] [type] of a [char1] and a [char2] who must [verb] a [obj] in [place]"
      They contain setting, characters, and action — exactly what image AI needs.
    - negative_prompt is film-agnostic: we always prohibit the same things.
    - Style can be chosen manually or detected automatically from genre.

Public API:
    build_prompt(title, genre, description, style='auto') -> tuple[str, str]
"""

# ── Style keyword database ────────────────────────────────────────────
# Each style maps to a list of visual descriptor phrases.
# These are appended to the base cinematic keywords.

_STYLE_KEYWORDS: dict[str, list[str]] = {
    'netflix': [
        'streaming platform poster quality',
        'bold cinematic composition',
        'dramatic dark atmosphere',
        'high contrast lighting',
    ],
    'disney': [
        'magical fairytale atmosphere',
        'vibrant warm color palette',
        'enchanting wonder-filled world',
        'timeless family-friendly art',
    ],
    'pixar': [
        '3D animated film aesthetic',
        'warm emotional lighting',
        'playful yet dramatic composition',
        'richly detailed animation art',
    ],
    'anime': [
        'Japanese animated film poster style',
        'detailed expressive illustration',
        'dynamic anime composition',
        'Studio Ghibli cinematic quality',
    ],
    'vintage': [
        'retro movie poster aesthetic',
        '1960s 1970s classic film art',
        'aged film grain texture',
        'muted earthy color palette',
        'old Hollywood composition',
    ],
    'dark': [
        'noir cinematic atmosphere',
        'dramatic chiaroscuro lighting',
        'moody dark color palette',
        'deep shadows and tension',
        'brooding ominous tone',
    ],
    'sci-fi': [
        'science fiction epic aesthetic',
        'neon metallic color palette',
        'futuristic environment',
        'space opera visual grandeur',
        'technological dystopian style',
    ],
    'colorful': [
        'vibrant energetic color palette',
        'dynamic lively composition',
        'bright cheerful atmosphere',
        'fun and expressive visual style',
    ],
    'art-house': [
        'European arthouse cinema aesthetic',
        'minimalist symbolic composition',
        'contemplative atmospheric tone',
        'poetic visual storytelling',
    ],
}

# ── Genre → style auto-mapping ────────────────────────────────────────
# When style='auto', the genre determines which style keywords to use.
# Genre names match the Sakila `category` table values (case-insensitive).

_GENRE_TO_STYLE: dict[str, str] = {
    'action':      'dark',
    'horror':      'dark',
    'thriller':    'dark',
    'drama':       'netflix',
    'new':         'netflix',
    'comedy':      'colorful',
    'music':       'colorful',
    'sports':      'colorful',
    'animation':   'pixar',
    'family':      'disney',
    'children':    'disney',
    'sci-fi':      'sci-fi',
    'games':       'sci-fi',
    'romance':     'vintage',
    'documentary': 'vintage',
    'classics':    'vintage',
    'travel':      'vintage',
    'foreign':     'art-house',
}

# ── Genre atmosphere phrases ──────────────────────────────────────────
# Short atmospheric descriptors added per genre to reinforce the mood.
# These are separate from style keywords — a 'dark' comedy still gets
# "comedic atmosphere" but also dark visual treatment.

_GENRE_ATMOSPHERE: dict[str, str] = {
    'action':      'explosive action-packed atmosphere',
    'horror':      'terrifying horror atmosphere, eerie unsettling mood',
    'thriller':    'suspenseful thriller atmosphere, psychological tension',
    'drama':       'emotional dramatic atmosphere, human conflict',
    'comedy':      'comedic lighthearted atmosphere, humorous mood',
    'romance':     'romantic passionate atmosphere, emotional warmth',
    'sci-fi':      'vast science fiction universe, cosmic scale',
    'animation':   'animated vibrant world, imaginative setting',
    'family':      'heartwarming family adventure, wholesome atmosphere',
    'children':    'delightful colorful children story world',
    'documentary': 'authentic real-world atmosphere, journalistic gravitas',
    'music':       'musical rhythm and energy, performance atmosphere',
    'sports':      'athletic triumph and determination, competitive spirit',
    'foreign':     'culturally rich atmosphere, exotic setting',
    'classics':    'timeless classic cinema atmosphere, golden age film',
    'vintage':     'nostalgic period atmosphere, historical setting',
    'games':       'immersive gaming world, epic fantasy or futuristic',
    'travel':      'adventurous journey atmosphere, exotic landscapes',
}

# ── Base and negative prompts ─────────────────────────────────────────

_BASE_KEYWORDS: list[str] = [
    'cinematic movie poster',
    'professional film art',
    'dramatic composition',
    'award-winning visual design',
    'ultra high resolution',
    '8K quality',
    'masterful cinematography',
]

# negative_prompt is film-agnostic — always prohibit the same elements
_NEGATIVE_PROMPT: str = (
    'text, letters, words, numbers, title text, movie title, '
    'logos, watermarks, signatures, stamps, '
    'real people, real celebrities, real actors, recognizable faces, '
    'subtitles, captions, credits, '
    'borders, frames, UI elements, interface, '
    'low quality, blurry, pixelated, distorted, artifacts, noise, '
    'poorly drawn, bad anatomy, ugly, deformed'
)


# ── Public API ────────────────────────────────────────────────────────

def build_prompt(
    title: str,
    genre: str,
    description: str,
    style: str = 'auto',
) -> tuple[str, str]:
    """
    Build a cinematic image prompt from film metadata.

    Args:
        title:       Film title (e.g. 'ACADEMY DINOSAUR').
        genre:       Genre name matching Sakila category (e.g. 'Action').
        description: Sakila film description. Contains setting, characters,
                     and plot — valuable visual material for the AI.
        style:       Visual style. Use 'auto' to detect from genre.
                     Options: 'netflix', 'disney', 'pixar', 'anime',
                              'vintage', 'dark', 'sci-fi', 'colorful',
                              'art-house', 'auto'.

    Returns:
        (prompt, negative_prompt) — both ready for any AI image provider.
    """
    resolved_style = _resolve_style(style, genre)
    genre_lower = (genre or '').lower()

    parts: list[str] = []

    # 1. Base cinematic keywords
    parts.extend(_BASE_KEYWORDS)

    # 2. Style-specific keywords
    parts.extend(_STYLE_KEYWORDS.get(resolved_style, []))

    # 3. Genre atmosphere
    atmosphere = _GENRE_ATMOSPHERE.get(genre_lower, '')
    if atmosphere:
        parts.append(atmosphere)

    # 4. Description themes — the most unique part per film.
    #    Sakila descriptions contain setting and characters — great for AI.
    if description:
        theme = _extract_theme(description)
        if theme:
            parts.append(f"inspired by: {theme}")

    # 5. Title hint — helps AI focus on the subject without adding text
    if title:
        parts.append(f"visual subject based on '{title}'")

    prompt = ', '.join(filter(None, parts))
    return prompt, _NEGATIVE_PROMPT


def resolve_style_for_genre(genre: str) -> str:
    """
    Return the visual style that would be auto-selected for this genre.
    Useful for logging and debugging.
    """
    return _resolve_style('auto', genre)


# ── Private helpers ───────────────────────────────────────────────────

def _resolve_style(style: str, genre: str) -> str:
    """
    Resolve 'auto' to a concrete style name using the genre mapping.
    Unknown genres fall back to 'netflix' (neutral, cinematic default).
    """
    if style and style != 'auto':
        return style if style in _STYLE_KEYWORDS else 'netflix'
    genre_lower = (genre or '').lower()
    return _GENRE_TO_STYLE.get(genre_lower, 'netflix')


def _extract_theme(description: str, max_chars: int = 200) -> str:
    """
    Extract the visual theme from a Sakila film description.

    Sakila descriptions follow a formula:
        "A [adj] [type] of a [char1] and a [char2] who must [verb] [obj] in [place]"

    We take the full description (up to max_chars) — AI models parse
    natural language well and extract setting, characters, and action.
    """
    cleaned = description.strip()
    if len(cleaned) > max_chars:
        # Cut at the last space before the limit to avoid splitting words
        cleaned = cleaned[:max_chars].rsplit(' ', 1)[0] + '...'
    return cleaned