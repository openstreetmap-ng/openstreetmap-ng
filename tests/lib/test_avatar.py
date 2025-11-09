from random import Random

import pytest

from app.lib.avatar import (
    _contrast_ratio,
    _extract_initials,
    _generate_accessible_color,
    _hsl_to_rgb,
    _relative_luminance,
)


def test_hsl_to_rgb():
    # Test primary colors
    assert _hsl_to_rgb(0, 1, 0.5) == 'ff0000'  # Red
    assert _hsl_to_rgb(120, 1, 0.5) == '00ff00'  # Green
    assert _hsl_to_rgb(240, 1, 0.5) == '0000ff'  # Blue

    # Test grayscale (saturation = 0)
    assert _hsl_to_rgb(0, 0, 0) == '000000'  # Black
    assert _hsl_to_rgb(0, 0, 0.5) == '808080'  # Gray (0.5 * 255 = 127.5, rounds to 128)
    assert _hsl_to_rgb(0, 0, 1) == 'ffffff'  # White

    # Test various hues
    assert _hsl_to_rgb(60, 1, 0.5) == 'ffff00'  # Yellow
    assert _hsl_to_rgb(180, 1, 0.5) == '00ffff'  # Cyan
    assert _hsl_to_rgb(300, 1, 0.5) == 'ff00ff'  # Magenta


def test_relative_luminance():
    # Test known luminance values
    assert _relative_luminance('ffffff') == pytest.approx(1.0, abs=0.01)  # White
    assert _relative_luminance('000000') == pytest.approx(0.0, abs=0.01)  # Black
    assert _relative_luminance('ff0000') == pytest.approx(0.2126, abs=0.01)  # Red
    assert _relative_luminance('00ff00') == pytest.approx(0.7152, abs=0.01)  # Green
    assert _relative_luminance('0000ff') == pytest.approx(0.0722, abs=0.01)  # Blue


def test_contrast_ratio():
    # White vs Black should be 21:1
    white_lum = 1.0
    black_lum = 0.0
    assert _contrast_ratio(white_lum, black_lum) == pytest.approx(21.0, abs=0.1)

    # Same color should be 1:1
    assert _contrast_ratio(0.5, 0.5) == pytest.approx(1.0, abs=0.01)

    # Test order independence
    assert _contrast_ratio(white_lum, black_lum) == _contrast_ratio(
        black_lum, white_lum
    )


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
