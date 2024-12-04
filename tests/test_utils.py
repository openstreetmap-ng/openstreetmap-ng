import pytest

from app.utils import extend_query_params, secure_referer, unicode_normalize


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        # already in NFC form
        ('naïve café', 'naïve café'),
        # NFD to NFC (diacritics separated)
        ('nai\u0308ve cafe\u0301', 'naïve café'),
        ('', ''),
    ],
)
def test_unicode_normalize(text, expected):
    assert unicode_normalize(text) == expected


@pytest.mark.parametrize(
    ('uri', 'params', 'expected', 'expected_fragment'),
    [
        (
            'http://example.com/',
            {},
            'http://example.com/',
            'http://example.com/',
        ),
        (
            'http://example.com',
            {'key': 'value'},
            'http://example.com?key=value',
            'http://example.com#key=value',
        ),
        (
            'http://example.com/',
            {'key1': 'value1', 'key2': 'value2'},
            'http://example.com/?key1=value1&key2=value2',
            'http://example.com/#key1=value1&key2=value2',
        ),
        (
            'http://example.com/?key1=value1',
            {'key2': 'value2'},
            'http://example.com/?key1=value1&key2=value2',
            'http://example.com/?key1=value1#key2=value2',
        ),
        (
            'http://example.com/?key1=value1',
            {'key1': 'new_value1'},
            'http://example.com/?key1=value1&key1=new_value1',
            'http://example.com/?key1=value1#key1=new_value1',
        ),
        (
            'http://example.com/',
            {'key with space': 'value with space'},
            'http://example.com/?key+with+space=value+with+space',
            'http://example.com/#key+with+space=value+with+space',
        ),
        (
            'http://example.com:8080/path;params?query#fragment',
            {'key': 'value'},
            'http://example.com:8080/path;params?query=&key=value#fragment',
            'http://example.com:8080/path;params?query#fragment=&key=value',
        ),
    ],
)
def test_extend_query_params(uri, params, expected, expected_fragment):
    assert extend_query_params(uri, params) == expected
    assert extend_query_params(uri, params, fragment=True) == expected_fragment


@pytest.mark.parametrize(
    ('referer', 'expected'),
    [
        (None, '/'),
        ('https://example.com', '/'),
        ('https://example.com/test', '/'),
        ('/test', '/test'),
        ('/test?key=value', '/test?key=value'),
    ],
)
def test_secure_referer(referer: str | None, expected: str):
    assert secure_referer(referer) == expected
