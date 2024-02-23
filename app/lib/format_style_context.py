from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import Request

from app.models.format_style import FormatStyle

_context = ContextVar('Format_context')


@contextmanager
def format_style_context(request: Request):
    """
    Context manager for setting the format style in ContextVar.

    Format style is auto-detected from the request.
    """

    request_path = request.url.path

    # path defaults
    if request_path.startswith(('/api/web/', '/api/0.7/')):
        style = FormatStyle.json
    elif request_path.startswith('/api/'):
        style = FormatStyle.xml
    else:
        style = FormatStyle.json

    extension = request_path.rpartition('.')[2]

    # overrides
    if extension == 'json':
        style = FormatStyle.json
    elif extension == 'xml':
        style = FormatStyle.xml
    elif extension == 'rss' or request_path.endswith('/feed'):
        style = FormatStyle.rss
    elif extension == 'gpx':
        style = FormatStyle.gpx

    token = _context.set(style)
    try:
        yield
    finally:
        _context.reset(token)


def format_style() -> FormatStyle:
    """
    Get the configured format style.
    """

    return _context.get()


def format_is_json() -> bool:
    """
    Check if the format style is JSON.
    """

    return _context.get() == FormatStyle.json


def format_is_xml() -> bool:
    """
    Check if the format style is XML.
    """

    return _context.get() == FormatStyle.xml


def format_is_rss() -> bool:
    """
    Check if the format style is RSS.
    """

    return _context.get() == FormatStyle.rss
