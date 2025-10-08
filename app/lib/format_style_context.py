from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

import cython

from app.middlewares.request_context_middleware import get_request

FormatStyle = Literal['json', 'xml', 'rss', 'gpx']

_LEGACY_EXTENSION_FORMATS: dict[str, FormatStyle] = {
    'json': 'json',
    'xml': 'xml',
    'rss': 'rss',
    'gpx': 'gpx',
}

_CTX = ContextVar[FormatStyle]('FormatStyle')


@contextmanager
def format_style_context():
    """
    Context manager for setting the format style in ContextVar.
    Format style is auto-detected from the request.
    """
    path: str = get_request().url.path

    # path defaults
    is_modern_api: cython.bint = (
        not path.startswith('/api/')  #
        or path.startswith(('/api/web/', '/api/0.7/'))
    )
    style: FormatStyle = (
        'rss'
        if path.endswith('/feed')  #
        else ('json' if is_modern_api else 'xml')
    )

    # extension overrides (legacy)
    if not is_modern_api:
        style = _LEGACY_EXTENSION_FORMATS.get(path.rsplit('.', 1)[-1], style)

    token = _CTX.set(style)
    try:
        yield
    finally:
        _CTX.reset(token)


def format_style() -> FormatStyle:
    """Get the configured format style."""
    return _CTX.get()


def format_is_json() -> bool:
    """Check if the format style is JSON."""
    return _CTX.get() == 'json'


def format_is_xml() -> bool:
    """Check if the format style is XML."""
    return _CTX.get() == 'xml'


def format_is_rss() -> bool:
    """Check if the format style is RSS."""
    return _CTX.get() == 'rss'


def format_is_gpx() -> bool:
    """Check if the format style is GPX."""
    return _CTX.get() == 'gpx'
