"""
prompt_builder — чистые функции для построения промпта AI-изображения.

Решения проектирования:
    - Чистые функции: без состояния, без побочных эффектов, без классов.
      Одинаковые входные данные всегда дают одинаковый результат. Легко тестировать.
    - Только английский: все основные модели AI-изображений обучены на английском
      тексте. Промпты не на английском дают результат более низкого качества.
    - Описания Sakila шаблонные, но полезные:
        "A [adj] [type] of a [char1] and a [char2] who must [verb] a [obj] in [place]"
      Они содержат сеттинг, персонажей и действие — именно то, что нужно image-AI.
    - negative_prompt не зависит от фильма: мы всегда запрещаем одно и то же.
    - Стиль можно выбрать вручную или определить автоматически по жанру.

Публичный API:
    build_prompt(title, genre, description, style='auto') -> tuple[str, str]
"""

# ── База ключевых слов стилей ────────────────────────────────────────
# Каждый стиль сопоставлен со списком фраз-визуальных дескрипторов.
# Они добавляются к базовым кинематографическим ключевым словам.
# ВАЖНО: фразы намеренно на английском — см. docstring модуля выше
# (модели AI-изображений обучены на английском, перевод ухудшит качество генерации).

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

# ── Авто-сопоставление жанр → стиль ────────────────────────────────────
# Когда style='auto', жанр определяет, какие ключевые слова стиля использовать.
# Названия жанров совпадают со значениями таблицы `category` Sakila
# (регистр не важен).

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

# ── Фразы атмосферы по жанрам ──────────────────────────────────────────
# Короткие атмосферные дескрипторы, добавляемые для каждого жанра,
# чтобы усилить настроение. Они отдельны от ключевых слов стиля —
# «мрачная» комедия всё равно получает "comedic atmosphere",
# но и мрачную визуальную обработку тоже.
# ВАЖНО: фразы намеренно на английском — см. docstring модуля выше.

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

# ── Базовый и негативный промпты ─────────────────────────────────────────

_BASE_KEYWORDS: list[str] = [
    'cinematic movie poster',
    'professional film art',
    'dramatic composition',
    'award-winning visual design',
    'ultra high resolution',
    '8K quality',
    'masterful cinematography',
]

# Слова из названий Sakila, из-за которых OpenAI отклонял генерацию
# (content policy) — подтверждено на практике для SHREK LICENSE,
# CITIZEN SHREK, PINOCCHIO SIMON, BANGER PINOCCHIO, LEGEND JEDI (все
# 5 провалившихся попыток из 1001 фильма содержали ровно одно из этих
# слов). Список точечный, а не общий список франшиз: другие похожие
# имена (POTTER, ZORRO, TARZAN, ALADDIN, GOLDFINGER, MULAN и т.д.)
# генерировались через OpenAI без проблем.
_BLOCKED_TITLE_WORDS: frozenset[str] = frozenset({'SHREK', 'JEDI', 'PINOCCHIO'})

# negative_prompt не зависит от фильма — всегда запрещаем одни и те же элементы
_NEGATIVE_PROMPT: str = (
    'text, letters, words, numbers, title text, movie title, '
    'logos, watermarks, signatures, stamps, '
    'real people, real celebrities, real actors, recognizable faces, '
    'subtitles, captions, credits, '
    'borders, frames, UI elements, interface, '
    'low quality, blurry, pixelated, distorted, artifacts, noise, '
    'poorly drawn, bad anatomy, ugly, deformed'
)


# ── Публичный API ────────────────────────────────────────────────────────

def build_prompt(
    title: str,
    genre: str,
    description: str,
    style: str = 'auto',
) -> tuple[str, str]:
    """
    Строит кинематографический промпт изображения из метаданных фильма.

    Аргументы:
        title:       Название фильма (например, 'ACADEMY DINOSAUR').
        genre:       Название жанра, совпадающее с категорией Sakila (например, 'Action').
        description: Описание фильма из Sakila. Содержит сеттинг, персонажей
                     и сюжет — ценный визуальный материал для AI.
        style:       Визуальный стиль. 'auto' определяет по жанру.
                     Варианты: 'netflix', 'disney', 'pixar', 'anime',
                              'vintage', 'dark', 'sci-fi', 'colorful',
                              'art-house', 'auto'.

    Возвращает:
        (prompt, negative_prompt) — оба готовы для любого AI-провайдера изображений.
    """
    resolved_style = _resolve_style(style, genre)
    genre_lower = (genre or '').lower()

    parts: list[str] = []

    # 1. Базовые кинематографические ключевые слова
    parts.extend(_BASE_KEYWORDS)

    # 2. Ключевые слова конкретного стиля
    parts.extend(_STYLE_KEYWORDS.get(resolved_style, []))

    # 3. Атмосфера жанра
    atmosphere = _GENRE_ATMOSPHERE.get(genre_lower, '')
    if atmosphere:
        parts.append(atmosphere)

    # 4. Темы из описания — самая уникальная часть для каждого фильма.
    #    Описания Sakila содержат сеттинг и персонажей — отлично для AI.
    if description:
        theme = _extract_theme(description)
        if theme:
            parts.append(f"inspired by: {theme}")

    # 5. Подсказка по названию — помогает AI сфокусироваться на сюжете без добавления текста.
    #    Слова из _BLOCKED_TITLE_WORDS вырезаются перед отправкой в промпт.
    if title:
        safe_title = _strip_blocked_words(title)
        if safe_title:
            parts.append(f"visual subject based on '{safe_title}'")

    prompt = ', '.join(filter(None, parts))
    return prompt, _NEGATIVE_PROMPT


def resolve_style_for_genre(genre: str) -> str:
    """
    Возвращает визуальный стиль, который был бы автоматически выбран для этого жанра.
    Полезно для логирования и отладки.
    """
    return _resolve_style('auto', genre)


# ── Приватные вспомогательные функции ───────────────────────────────────────────

def _resolve_style(style: str, genre: str) -> str:
    """
    Преобразует 'auto' в конкретное название стиля через сопоставление жанров.
    Неизвестные жанры откатываются на 'netflix' (нейтральный кинематографический вариант).
    """
    if style and style != 'auto':
        return style if style in _STYLE_KEYWORDS else 'netflix'
    genre_lower = (genre or '').lower()
    return _GENRE_TO_STYLE.get(genre_lower, 'netflix')


def _strip_blocked_words(title: str) -> str:
    """
    Убирает из названия слова из _BLOCKED_TITLE_WORDS перед вставкой в промпт.

    Например, 'SHREK LICENSE' -> 'LICENSE', 'CITIZEN SHREK' -> 'CITIZEN'.
    Если после фильтрации ничего не остаётся, возвращает пустую строку —
    вызывающий код в этом случае просто не добавляет строку с названием.
    """
    words = [w for w in title.split() if w.upper() not in _BLOCKED_TITLE_WORDS]
    return ' '.join(words)


def _extract_theme(description: str, max_chars: int = 200) -> str:
    """
    Извлекает визуальную тему из описания фильма Sakila.

    Описания Sakila следуют шаблону:
        "A [adj] [type] of a [char1] and a [char2] who must [verb] [obj] in [place]"

    Берём полное описание (до max_chars) — модели AI хорошо разбирают
    естественный язык и извлекают сеттинг, персонажей и действие.
    """
    cleaned = description.strip()
    if len(cleaned) > max_chars:
        # Обрезаем на последнем пробеле перед лимитом, чтобы не разрывать слова
        cleaned = cleaned[:max_chars].rsplit(' ', 1)[0] + '...'
    return cleaned
