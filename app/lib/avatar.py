import logging
import random
import re
import unicodedata
from html import escape
from typing import Literal

from pydantic import SecretStr

from app.config import DYNAMIC_AVATAR_CACHE_EXPIRE
from app.lib.crypto import hash_storage_key
from app.models.types import StorageKey
from app.services.cache_service import CacheContext, CacheService

_AvatarStyle = Literal['initials', 'shapes']

_CTX = CacheContext('Avatar')
_WORD_BOUNDARY_RE = re.compile(r'[\s\-_.,;:!?@/\\()\[\]{}0-9]+')
_CAMEL_CASE_RE = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')

# Color palettes matching dicebear's Material Design colors
_INITIALS_BG_COLORS = [
    'e53935', 'd81b60', '8e24aa', '5e35b1', '3949ab', '1e88e5',
    '039be5', '00acc1', '00897b', '43a047', '7cb342', 'c0ca33',
    'fdd835', 'ffb300', 'fb8c00', 'f4511e',
]

_SHAPES_COLORS = [
    '0a5b83', '1c799f', '69d2e7', 'f1f4dc', 'f88c49',
]

# Shape definitions as SVG paths (viewBox 0 0 100 100)
_SHAPE_DEFS = {
    'rectangle': '<path fill-rule="evenodd" clip-rule="evenodd" d="M90 10H10v80h80V10ZM0 0v100h100V0H0Z" fill="#{color}"/>',
    'rectangleFilled': '<path d="M0 0h100v100H0V0Z" fill="#{color}"/>',
    'ellipse': '<path fill-rule="evenodd" clip-rule="evenodd" d="M50 90a40 40 0 1 0 0-80 40 40 0 0 0 0 80Zm0 10A50 50 0 1 0 50 0a50 50 0 0 0 0 100Z" fill="#{color}"/>',
    'ellipseFilled': '<path d="M100 50A50 50 0 1 1 0 50a50 50 0 0 1 100 0Z" fill="#{color}"/>',
    'polygon': '<path fill-rule="evenodd" clip-rule="evenodd" d="M50 7 0 93.6h100L50 7Zm0 20L17.3 83.6h65.4L50 27Z" fill="#{color}"/>',
    'polygonFilled': '<path d="m50 7 50 86.6H0L50 7Z" fill="#{color}"/>',
    'line': '<path fill="#{color}" d="M45-150h10v400H45z"/>',
}


async def generate_avatar(style: _AvatarStyle, text: str | SecretStr, /) -> bytes:
    """Generate a random avatar SVG."""
    cache_key = hash_storage_key(
        f'{style}/{text.get_secret_value() if isinstance(text, SecretStr) else text}',
        '.svg',
    )

    async def factory() -> bytes:
        return _generate_avatar_impl(style, text, cache_key)

    return await CacheService.get(
        cache_key, _CTX, factory, ttl=DYNAMIC_AVATAR_CACHE_EXPIRE
    )


def _generate_avatar_impl(
    style: _AvatarStyle, text: str | SecretStr, cache_key: StorageKey, /
) -> bytes:
    """Generate avatar implementation (synchronous)."""
    if style == 'initials':
        assert not isinstance(text, SecretStr), (
            'initials style must not be used with SecretStr'
        )
        svg = _generate_initials(text, cache_key)
    else:  # shapes
        svg = _generate_shapes(cache_key)

    logging.debug('Avatar generated successfully: style=%r', style)
    return svg.encode()


def _generate_initials(text: str, cache_key: StorageKey) -> str:
    """
    Generate an initials-based avatar.

    Creates a colorful circle with 1-2 character initials centered.
    """
    initials = _extract_initials(text)

    # Use cache_key as seed for deterministic color selection
    rng = random.Random(cache_key)
    bg_color = rng.choice(_INITIALS_BG_COLORS)

    # Calculate text position (dy offset for vertical centering)
    # Based on dicebear's formula: dy = fontSize * 0.356
    font_size = 50
    dy = font_size * 0.356

    # Escape initials for XML
    escaped_initials = escape(initials, quote=True)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none">
  <rect width="100" height="100" rx="50" fill="#{bg_color}"/>
  <text x="50" y="50" font-family="Arial, sans-serif" font-size="{font_size}" font-weight="400" fill="#ffffff" text-anchor="middle" dy="{dy:.3f}">{escaped_initials}</text>
</svg>'''

    return svg


def _generate_shapes(cache_key: StorageKey) -> str:
    """
    Generate a shapes-based avatar.

    Creates 3 overlapping geometric shapes with random colors, positions, and rotations.
    """
    rng = random.Random(cache_key)

    # Pick background color
    bg_color = rng.choice(_SHAPES_COLORS)

    # Layer 1: Large shape (scale 1.2, offset range ±65/±45, rotation ±160)
    shape1_types = ['rectangleFilled', 'ellipseFilled', 'polygonFilled']
    shape1 = rng.choice(shape1_types)
    color1 = rng.choice(_SHAPES_COLORS)
    offset1_x = rng.randint(-65, 65)
    offset1_y = rng.randint(-45, 45)
    rotation1 = rng.randint(-160, 160)

    # Layer 2: Medium shape (scale 0.8, offset range ±40/±40, rotation ±180)
    shape2_types = ['rectangleFilled', 'ellipseFilled', 'polygonFilled', 'line']
    shape2 = rng.choice(shape2_types)
    color2 = rng.choice(_SHAPES_COLORS)
    offset2_x = rng.randint(-40, 40)
    offset2_y = rng.randint(-40, 40)
    rotation2 = rng.randint(-180, 180)

    # Layer 3: Small shape (scale 0.4, offset range ±25/±25, rotation ±180)
    shape3_types = list(_SHAPE_DEFS.keys())
    shape3 = rng.choice(shape3_types)
    color3 = rng.choice(_SHAPES_COLORS)
    offset3_x = rng.randint(-25, 25)
    offset3_y = rng.randint(-25, 25)
    rotation3 = rng.randint(-180, 180)

    # Generate shape SVG elements
    shape1_svg = _SHAPE_DEFS[shape1].format(color=color1)
    shape2_svg = _SHAPE_DEFS[shape2].format(color=color2)
    shape3_svg = _SHAPE_DEFS[shape3].format(color=color3)

    # Compose final SVG with transforms
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="none" shape-rendering="auto">
  <rect width="100" height="100" fill="#{bg_color}"/>
  <g transform="matrix(1.2 0 0 1.2 -10 -10)">
    <g transform="translate(50 50) rotate({rotation1}) translate({offset1_x} {offset1_y}) translate(-50 -50)">
      {shape1_svg}
    </g>
  </g>
  <g transform="matrix(.8 0 0 .8 10 10)">
    <g transform="translate(50 50) rotate({rotation2}) translate({offset2_x} {offset2_y}) translate(-50 -50)">
      {shape2_svg}
    </g>
  </g>
  <g transform="matrix(.4 0 0 .4 30 30)">
    <g transform="translate(50 50) rotate({rotation3}) translate({offset3_x} {offset3_y}) translate(-50 -50)">
      {shape3_svg}
    </g>
  </g>
</svg>'''

    return svg


def _extract_initials(text: str) -> str:
    """
    Extract initials from text with enhanced unicode support.

    Rules:
    1. Split by word boundaries (spaces, hyphens, underscores, etc.)
    2. If no word boundaries, check for camelCase
    3. Take first alphabetic character from each part (ignoring numbers)
    4. If no boundaries found, take first 2 alphabetic characters
    5. Always return exactly 2 uppercase characters
    6. If only 1 character extracted, double it
    7. Properly handle unicode letters including combining marks
    """
    if not text:
        return 'XX'

    # Normalize unicode to NFC form for consistent handling
    text = unicodedata.normalize('NFC', text)

    # First, try to split by word boundaries
    parts: list[str] = [p for p in _WORD_BOUNDARY_RE.split(text) if p]
    part: str
    char: str

    initials: list[str] = []

    if len(parts) >= 2:
        # Multiple parts found - take first alphabetic from each
        for part in parts:
            if len(initials) >= 2:
                break
            for char in part:
                if char.isalpha():
                    initials.append(char)
                    break
    elif parts:
        # Single part - check for camelCase
        part = parts[0]
        camel_parts: list[str] = _CAMEL_CASE_RE.split(part)

        if len(camel_parts) >= 2:
            # CamelCase detected - take first alpha from each part
            for part in camel_parts:
                if len(initials) >= 2:
                    break
                for char in part:
                    if char.isalpha():
                        initials.append(char)
                        break
        else:
            # No boundaries - take first 2 alphabetic chars
            for char in part:
                if char.isalpha():
                    initials.append(char)
                    if len(initials) >= 2:
                        break
    else:
        # No parts after splitting - process original text
        for char in text:
            if char.isalpha():
                initials.append(char)
                if len(initials) >= 2:
                    break

    if not initials:
        return 'XX'

    return (
        initials[0] + initials[1]  #
        if len(initials) >= 2
        else initials[0] + initials[0]
    ).upper()
