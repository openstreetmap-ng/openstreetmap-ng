import pytest

from app.validators.url import _validate_url_safe, parse_uri


@pytest.mark.parametrize(
    ('uri_str', 'valid'),
    [
        ('http://example.com', True),
        ('https://example.com', True),
        ('ftp://example.com', True),  # Additional scheme allowed
        ('ssh://example.com', True),  # Additional scheme allowed
        ('http://[::1]', True),  # IPv6
        ('http://127.0.0.1', True),
        ('http://user@example.com', True),  # User but no password
        ('example.com', False),  # Missing scheme
        ('http://', False),  # Missing host
        ('http://user:password@example.com', False),  # Contains password
    ],
)
def test_parse_uri(uri_str, valid):
    try:
        parse_uri(uri_str)
        assert valid
    except Exception:
        assert not valid


@pytest.mark.parametrize(
    ('value', 'valid'),
    [
        ('example', True),
        ('URL-Safe Name', True),
        ('example/path', False),
        ('name.surname', False),
        ('query?param', False),
        ('hash#tag', False),
    ],
)
def test_url_safe_validator(value, valid):
    try:
        _validate_url_safe(value)
        assert valid
    except Exception:
        assert not valid
