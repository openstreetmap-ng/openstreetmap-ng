from random import Random

import pytest

from app.lib.avatar import (
    _contrast_ratio,
    _extract_initials,
    _generate_accessible_color,
    _hsl_to_rgb,
    _relative_luminance,
)


@pytest.mark.parametrize(
    ('h', 's', 'l', 'expected'),
    [
        (0, 1, 0.5, 'ff0000'),  # Red
        (120, 1, 0.5, '00ff00'),  # Green
        (240, 1, 0.5, '0000ff'),  # Blue
        (0, 0, 0, '000000'),  # Black
        (0, 0, 0.5, '808080'),  # Gray
        (0, 0, 1, 'ffffff'),  # White
        (60, 1, 0.5, 'ffff00'),  # Yellow
        (180, 1, 0.5, '00ffff'),  # Cyan
        (300, 1, 0.5, 'ff00ff'),  # Magenta
    ],
)
def test_hsl_to_rgb(h: float, s: float, l: float, expected: str):
    assert _hsl_to_rgb(h, s, l) == expected


@pytest.mark.parametrize(
    ('color', 'expected'),
    [
        ('ffffff', 1.0),  # White
        ('000000', 0.0),  # Black
        ('ff0000', 0.2126),  # Red
        ('00ff00', 0.7152),  # Green
        ('0000ff', 0.0722),  # Blue
    ],
)
def test_relative_luminance(color: str, expected: float):
    assert _relative_luminance(color) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize(
    ('l1', 'l2', 'expected'),
    [
        (1.0, 0.0, 21.0),  # White vs Black
        (0.5, 0.5, 1.0),  # Same color
        (0.0, 1.0, 21.0),  # Order independence (Black vs White)
    ],
)
def test_contrast_ratio(l1: float, l2: float, expected: float):
    assert _contrast_ratio(l1, l2) == pytest.approx(expected, abs=0.1)


def test_generate_accessible_color_meets_wcag_aa():
    """Test that generated colors meet WCAG AA standard (4.5:1 contrast)."""
    rng = Random(42)
    white_luminance = 1.0
    min_contrast = 4.5

    # Test 100 random seeds to ensure consistency
    for seed in range(100):
        rng = Random(seed)
        color = _generate_accessible_color(rng)

        # Verify it's a valid hex color
        assert len(color) == 6
        int(color, 16)  # Should not raise

        # Verify contrast meets WCAG AA
        color_luminance = _relative_luminance(color)
        contrast = _contrast_ratio(white_luminance, color_luminance)
        assert contrast >= min_contrast, (
            f'Color #{color} has contrast {contrast:.2f}, expected >= {min_contrast}'
        )


def test_generate_accessible_color_deterministic():
    """Test that same seed produces same color."""
    rng1 = Random(12345)
    rng2 = Random(12345)

    color1 = _generate_accessible_color(rng1)
    color2 = _generate_accessible_color(rng2)

    assert color1 == color2


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        # Basic space-separated names
        ('Abc Def Ghi', 'AD'),
        ('abc DEF ghi', 'AD'),
        ('John Doe', 'JD'),
        ('alice bob charlie', 'AB'),
        # CamelCase patterns
        ('abcDEF', 'AD'),
        ('ABCdef', 'AC'),
        ('CamelCase', 'CC'),
        ('HTTPSConnection', 'HC'),
        ('XMLHttpRequest', 'XH'),
        # No boundaries - take first 2 chars
        ('abcdef', 'AB'),
        ('13northy', 'NO'),
        ('username', 'US'),
        # Special characters and delimiters
        ('A-13', 'AA'),  # Numbers ignored
        ('B_55', 'BB'),  # Numbers ignored
        ('my-awesome_project', 'MA'),
        ('user@email.com', 'UE'),
        ('hello.world', 'HW'),
        ('one/two/three', 'OT'),
        # Single character cases
        ('a', 'AA'),
        ('Z', 'ZZ'),
        ('5', 'XX'),
        # Double character cases
        ('AA', 'AA'),
        ('ab', 'AB'),
        ('XY', 'XY'),
        # Unicode support
        ('北京市', '北京'),
        ('Москва', 'МО'),  # noqa: RUF001
        ('Αθήνα', 'ΑΘ'),
        ('مدينة', 'مد'),
        # Mixed patterns
        ('user123name', 'UN'),  # Numbers act as boundaries: user|name
        ('123abc456def', 'AD'),  # Numbers act as boundaries: abc|def
        ('test_123_case', 'TC'),
        ('(hello) world!', 'HW'),
        ('[Special] Case', 'SC'),
        # Edge cases
        ('', 'XX'),  # Empty string
        ('123456', 'XX'),  # All numbers
        ('!@#$%^', 'XX'),  # All special chars
        ('   ', 'XX'),  # Only spaces
        ('a1b2c3', 'AB'),  # Alternating letters/numbers
    ],
)
def test_extract_initials(text: str, expected: str):
    assert _extract_initials(text) == expected
