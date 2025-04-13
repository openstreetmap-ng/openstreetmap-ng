import pytest

from app.utils import extend_query_params, splitlines_trim


@pytest.mark.parametrize(
    ('uri', 'params', 'expected', 'expected_fragment'),
    [
        (
            'https://example.com/',
            {},
            'https://example.com/',
            'https://example.com/',
        ),
        (
            'https://example.com',
            {'key': 'value'},
            'https://example.com?key=value',
            'https://example.com#key=value',
        ),
        (
            'https://example.com/',
            {'key1': 'value1', 'key2': 'value2'},
            'https://example.com/?key1=value1&key2=value2',
            'https://example.com/#key1=value1&key2=value2',
        ),
        (
            'https://example.com/?key1=value1',
            {'key2': 'value2'},
            'https://example.com/?key1=value1&key2=value2',
            'https://example.com/?key1=value1#key2=value2',
        ),
        (
            'https://example.com/?key1=value1',
            {'key1': 'new_value1'},
            'https://example.com/?key1=value1&key1=new_value1',
            'https://example.com/?key1=value1#key1=new_value1',
        ),
        (
            'https://example.com/',
            {'key with space': 'value with space'},
            'https://example.com/?key+with+space=value+with+space',
            'https://example.com/#key+with+space=value+with+space',
        ),
        (
            'https://example.com:8080/path;params?query#fragment',
            {'key': 'value'},
            'https://example.com:8080/path;params?query=&key=value#fragment',
            'https://example.com:8080/path;params?query#fragment=&key=value',
        ),
    ],
)
def test_extend_query_params(uri, params, expected, expected_fragment):
    assert extend_query_params(uri, params) == expected
    assert extend_query_params(uri, params, fragment=True) == expected_fragment


@pytest.mark.parametrize(
    ('s', 'expected'),
    [
        ('', []),
        ('foo\n\nbar\n', ['foo', 'bar']),
        ('foo \n bar', ['foo', 'bar']),
    ],
)
def test_splitlines_trim(s, expected):
    assert splitlines_trim(s) == expected
