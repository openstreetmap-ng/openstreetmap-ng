from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

import cython

from app.middlewares.request_context_middleware import get_request

FormatStyle = Literal['json', 'xml', 'rss', 'gpx']

_CTX: ContextVar[FormatStyle] = ContextVar('FormatStyle')


@contextmanager
def format_style_context():
    """
    Context manager for setting the format style in ContextVar.

    Format style is auto-detected from the request.
    """
    request_path: str = get_request().url.path
    is_modern_api: cython.bint

    # path defaults
    if request_path.startswith(('/api/web/', '/api/partial/', '/api/0.7/')):
        is_modern_api = True
    elif request_path.startswith('/api/'):
        is_modern_api = False
    else:
        is_modern_api = True

    style: FormatStyle = 'json' if is_modern_api else 'xml'

    # path overrides
    if request_path.endswith('/feed'):
        style = 'rss'

    # extension overrides (legacy)
    if not is_modern_api:
        extension = request_path.rsplit('.', 1)[-1]
        if extension == 'json':
            style = 'json'
        elif extension == 'xml':
            style = 'xml'
        elif extension == 'rss':
            style = 'rss'
        elif extension == 'gpx':
            style = 'gpx'

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
