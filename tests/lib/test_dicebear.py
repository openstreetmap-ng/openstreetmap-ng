import pytest

from app.lib.dicebear import _extract_initials


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
        ('Москва', 'МО'),
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
