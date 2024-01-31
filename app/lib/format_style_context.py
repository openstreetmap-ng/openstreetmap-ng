from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import Request

from app.models.format_style import FormatStyle

_context = ContextVar('Format_context')

# read property once for performance
_style_json = FormatStyle.json
_style_xml = FormatStyle.xml
_style_rss = FormatStyle.rss
_style_gpx = FormatStyle.gpx


@contextmanager
def format_style_context(request: Request):
    """
    Context manager for setting the format style in ContextVar.

    Format style is auto-detected from the request.
    """

    request_path = request.url.path

    # path defaults
    if request_path.startswith('/api/0.7/'):
        style = _style_json
    elif request_path.startswith('/api/'):
        style = _style_xml
    else:
        style = _style_json

    extension = request_path.rpartition('.')[2]

    # overrides
    if extension == 'json':
        style = _style_json
    elif extension == 'xml':
        style = _style_xml
    elif extension == 'rss' or request_path.endswith('/feed'):
        style = _style_rss
    elif extension == 'gpx':
        style = _style_gpx

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

    return _context.get() == _style_json


def format_is_xml() -> bool:
    """
    Check if the format style is XML.
    """

    return _context.get() == _style_xml


def format_is_rss() -> bool:
    """
    Check if the format style is RSS.
    """

    return _context.get() == _style_rss
