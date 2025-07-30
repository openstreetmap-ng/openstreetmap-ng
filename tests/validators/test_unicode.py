import pytest

from app.validators.unicode import unicode_unquote_normalize


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        # Unicode normalization tests
        ('naïve café', 'naïve café'),  # Already normalized
        ('nai\u0308ve cafe\u0301', 'naïve café'),  # NFD to NFC (diacritics separated)
        ('', ''),
        # URL unquoting tests
        ('hello%20world', 'hello world'),  # %20 -> space
        ('test%2Bfile', 'test+file'),  # %2B -> +
        ('user%40example.com', 'user@example.com'),  # %40 -> @
        ('caf%C3%A9', 'café'),  # UTF-8 encoded é
        ('na%C3%AFve%20caf%C3%A9', 'naïve café'),  # UTF-8 encoded naïve café
        # Combined tests (URL-encoded + Unicode normalization)
        ('nai%CC%88ve%20cafe%CC%81', 'naïve café'),  # URL-encoded NFD -> NFC
        ('hello+world', 'hello world'),  # + is unquoted to space by unquote_plus
    ],
)
def test_unicode_normalize_and_unquote(text, expected):
    assert unicode_unquote_normalize(text) == expected
