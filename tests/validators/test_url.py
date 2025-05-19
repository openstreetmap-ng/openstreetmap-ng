import pytest
from rfc3986 import uri_reference

from app.validators.url import (
    UriValidator,
    UrlValidator,
    _validate_url_safe,  # noqa: PLC2701
)


@pytest.mark.parametrize(
    ('url', 'valid'),
    [
        ('http://example.com', True),
        ('https://example.com', True),
        ('http://example.com/path', True),
        ('https://example.com/path?query=value', True),
        ('https://example.com:8080', True),
        ('http://127.0.0.1', True),
        ('http://[::1]', True),  # IPv6
        ('http://user@example.com', True),  # User but no password
        ('ftp://example.com', False),  # Invalid scheme
        ('ssh://example.com', False),  # Invalid scheme
        ('example.com', False),  # Missing scheme
        ('http://', False),  # Missing host
        ('http://user:password@example.com', False),  # Contains password
    ],
)
def test_url_validator(url, valid):
    try:
        UrlValidator.validate(uri_reference(url))
        assert valid
    except Exception:
        assert not valid


@pytest.mark.parametrize(
    ('uri_str', 'valid'),
    [
        ('http://example.com', True),
        ('https://example.com', True),
        ('ftp://example.com', True),  # Additional scheme allowed
        ('ssh://example.com', True),  # Additional scheme allowed
        ('example.com', False),  # Missing scheme
        ('http://', False),  # Missing host
        ('http://user:password@example.com', False),  # Contains password
    ],
)
def test_uri_validator(uri_str, valid):
    try:
        UriValidator.validate(uri_reference(uri_str))
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
