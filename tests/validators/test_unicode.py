import pytest

from app.validators.unicode import unicode_normalize


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('naïve café', 'naïve café'),  # already in NFC form
        ('nai\u0308ve cafe\u0301', 'naïve café'),  # NFD to NFC (diacritics separated)
        ('', ''),
    ],
)
def test_unicode_normalize(text, expected):
    assert unicode_normalize(text) == expected
