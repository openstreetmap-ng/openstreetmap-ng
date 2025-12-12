import logging
from html import escape
from random import Random
from typing import Literal

import cython
import re2

from app.lib.crypto import hmac_bytes

_AvatarStyle = Literal['initials', 'shapes']


def generate_avatar(style: _AvatarStyle, text: str, /) -> bytes:
    """Generate a random avatar SVG."""
    if style == 'initials':
        svg = _generate_initials(text)
    else:  # shapes
        svg = _generate_shapes(hmac_bytes(text))

    logging.debug('Generated %r avatar', style)
    return svg.encode()


def _hsl_to_rgb(h: cython.double, s: cython.double, l: cython.double) -> str:
    """
    Convert HSL to RGB hex string.
    h: hue [0, 360)
    s: saturation [0, 1]
    l: lightness [0, 1]
    """
    c: cython.double = (1 - abs(2 * l - 1)) * s
    x: cython.double = c * (1 - abs((h / 60) % 2 - 1))
    m: cython.double = l - c / 2

    r1: cython.double
    g1: cython.double
    b1: cython.double
    if h < 60:
        r1, g1, b1 = c, x, 0
    elif h < 120:
        r1, g1, b1 = x, c, 0
    elif h < 180:
        r1, g1, b1 = 0, c, x
    elif h < 240:
        r1, g1, b1 = 0, x, c
    elif h < 300:
        r1, g1, b1 = x, 0, c
    else:
        r1, g1, b1 = c, 0, x

    r = round((r1 + m) * 255)
    g = round((g1 + m) * 255)
    b = round((b1 + m) * 255)
    return f'{r:02x}{g:02x}{b:02x}'


def _apca_luminance(rgb_hex: str) -> cython.double:
    """
    Calculate APCA screen luminance (Ys) with soft clip for blacks.
    https://github.com/Myndex/SAPC-APCA
    """
    S_TRC: cython.double = 2.4  # sRGB linearization exponent
    B_THRSH: cython.double = 0.022  # black soft clip threshold
    B_CLIP: cython.double = 1.414  # black soft clip exponent

    r: cython.double = (int(rgb_hex[0:2], 16) / 255) ** S_TRC
    g: cython.double = (int(rgb_hex[2:4], 16) / 255) ** S_TRC
    b: cython.double = (int(rgb_hex[4:6], 16) / 255) ** S_TRC

    y: cython.double = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b

    # Soft clip for black level
    if y < B_THRSH:
        y += (B_THRSH - y) ** B_CLIP
    return y


def _apca_contrast(y_txt: cython.double, y_bg: cython.double) -> cython.double:
    """
    Calculate APCA lightness contrast (Lc) between text and background.
    Returns signed value: positive = dark text on light bg, negative = light text on dark bg.
    """
    N_TX: cython.double = 0.57  # normal polarity text exponent
    N_BG: cython.double = 0.56  # normal polarity background exponent
    R_TX: cython.double = 0.62  # reverse polarity text exponent
    R_BG: cython.double = 0.65  # reverse polarity background exponent
    W_SCALE: cython.double = 1.14  # output scale
    W_OFFSET: cython.double = 0.027  # output offset
    W_CLAMP: cython.double = 0.1  # low contrast clamp threshold

    sapc: cython.double
    if y_bg > y_txt:
        # Normal polarity: dark text on light background
        sapc = (y_bg**N_BG - y_txt**N_TX) * W_SCALE
    else:
        # Reverse polarity: light text on dark background
        sapc = (y_bg**R_BG - y_txt**R_TX) * W_SCALE

    # Clamp and apply offset
    if abs(sapc) < W_CLAMP:
        return 0.0
    if sapc > 0:
        return (sapc - W_OFFSET) * 100.0
    return (sapc + W_OFFSET) * 100.0


def _generate_accessible_color(rng: Random) -> str:
    """
    Generate a random color with guaranteed contrast against white text.
    Uses HSL color space for better control over visual properties.
    Ensures APCA Lc >= 60 (equivalent to WCAG AA 4.5:1) for body text.
    """
    MIN_LC: cython.double = 60.0  # minimum APCA lightness contrast
    WHITE_Y: cython.double = 1.0  # white text luminance

    # Generate vibrant, accessible colors
    h = rng.random() * 360
    s = 0.5 + rng.random() * 0.3
    l = 0.3 + rng.random() * 0.35

    color = ''
    lc: cython.double = 0.0
    while abs(lc) < MIN_LC:
        color = _hsl_to_rgb(h, s, l)
        bg_y = _apca_luminance(color)
        lc = _apca_contrast(WHITE_Y, bg_y)  # white text on colored bg
        l *= 0.9  # Make darker

    return color


@cython.cfunc
def _generate_initials(text: str) -> str:
    """https://www.dicebear.com/styles/initials/"""
    rng = Random(text)
    font_size = 50
    dy = font_size * 0.356

    bg_color = _generate_accessible_color(rng)
    initials = escape(_extract_initials(text))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<rect width="100" height="100" fill="#{bg_color}"/>
<text x="50" y="50" font-family="Arial, sans-serif" font-size="{font_size}" fill="#fff" text-anchor="middle" dy="{dy:.3f}">{initials}</text>
</svg>'''


# Shape definitions as SVG paths (viewBox 0 0 100 100)
_SHAPE_DEFS = {
    'ellipse': '<path fill-rule="evenodd" clip-rule="evenodd" d="M50 90a40 40 0 1 0 0-80 40 40 0 0 0 0 80Zm0 10A50 50 0 1 0 50 0a50 50 0 0 0 0 100Z" fill="#{color}"/>',
    'ellipseFilled': '<path d="M100 50A50 50 0 1 1 0 50a50 50 0 0 1 100 0Z" fill="#{color}"/>',
    'line': '<path fill="#{color}" d="M45-150h10v400H45z"/>',
    'polygon': '<path fill-rule="evenodd" clip-rule="evenodd" d="M50 7 0 93.6h100L50 7Zm0 20L17.3 83.6h65.4L50 27Z" fill="#{color}"/>',
    'polygonFilled': '<path d="m50 7 50 86.6H0L50 7Z" fill="#{color}"/>',
    'rectangle': '<path fill-rule="evenodd" clip-rule="evenodd" d="M90 10H10v80h80V10ZM0 0v100h100V0H0Z" fill="#{color}"/>',
    'rectangleFilled': '<path d="M0 0h100v100H0V0Z" fill="#{color}"/>',
}


@cython.cfunc
def _generate_shapes(seed: int | float | str | bytes | bytearray) -> str:
    """https://www.dicebear.com/styles/shapes/"""
    rng = Random(seed)

    # Generate complementary harmony palette

    # Background: Primary
    primary_h = rng.random() * 360
    primary_s = 0.6 + rng.random() * 0.2
    primary_l = 0.7 + rng.random() * 0.1
    bg_color = _hsl_to_rgb(primary_h, primary_s, primary_l)

    # Large shape
    h = (primary_h + 30) % 360
    s = 0.6 + rng.random() * 0.1
    l = 0.35 + rng.random() * 0.2
    color1 = _hsl_to_rgb(h, s, l)

    # Medium shape
    h = (primary_h + 180) % 360
    s = 0.6 + rng.random() * 0.1
    l = 0.35 + rng.random() * 0.2
    color2 = _hsl_to_rgb(h, s, l)

    # Small shape
    color3 = _hsl_to_rgb(primary_h, primary_s, primary_l + 0.1)

    # Layer 1: Large shape (scale 1.2, offset range ±65/±45, rotation ±160)
    shape1 = rng.choice(('rectangleFilled', 'ellipseFilled', 'polygonFilled'))
    shape1_svg = _SHAPE_DEFS[shape1].format(color=color1)
    offset1_x = rng.randint(-65, 65)
    offset1_y = rng.randint(-45, 45)
    rotation1 = rng.randint(-160, 160)

    # Layer 2: Medium shape (scale 0.8, offset range ±40/±40, rotation ±180)
    shape2 = rng.choice(('rectangleFilled', 'ellipseFilled', 'polygonFilled', 'line'))
    shape2_svg = _SHAPE_DEFS[shape2].format(color=color2)
    offset2_x = rng.randint(-40, 40)
    offset2_y = rng.randint(-40, 40)
    rotation2 = rng.randint(-180, 180)

    # Layer 3: Small shape (scale 0.4, offset range ±25/±25, rotation ±180)
    shape3 = rng.choice(tuple(_SHAPE_DEFS))
    shape3_svg = _SHAPE_DEFS[shape3].format(color=color3)
    offset3_x = rng.randint(-25, 25)
    offset3_y = rng.randint(-25, 25)
    rotation3 = rng.randint(-180, 180)

    # Compose final SVG with transforms
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
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
</svg>"""


_WORD_BOUNDARY_RE = re2.compile(r'[\s\-_.,;:!?@/\\()\[\]{}0-9]+')
_CAMEL_CASE_BOUNDARY_RE = re2.compile(r'([a-z])([A-Z])|([A-Z])([A-Z][a-z])')


@cython.cfunc
def _split_camel_case(s: str) -> list[str]:
    """Split a string on camelCase / PascalCase boundaries."""
    if len(s) < 2:
        return [s]

    # Patterns:
    # - lower->upper: "fooBar" => "foo Bar"
    # - acronym->word: "JSONData" => "JSON Data"
    return _CAMEL_CASE_BOUNDARY_RE.sub(r'\1\3 \2\4', s).split()


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
        camel_parts = _split_camel_case(part)

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
