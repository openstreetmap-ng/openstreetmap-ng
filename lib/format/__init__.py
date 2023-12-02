from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import Request

from models.format_style import FormatStyle

# TODO: middleware for context
# TODO: 0.7 only &format
_context = ContextVar('Format_context')


@contextmanager
def format_style_context(request: Request):
    """
    Context manager for setting the format style in ContextVar.

    Format style is auto-detected from the request.
    """

    request_path = request.url.path

    # path defaults
    if request_path.startswith('/api/0.7/'):
        style = FormatStyle.json
    elif request_path.startswith('/api/'):
        style = FormatStyle.xml
    else:
        style = FormatStyle.json

    # overrides
    if request_path.endswith('.json'):
        style = FormatStyle.json
    elif request_path.endswith('.xml'):
        style = FormatStyle.xml
    elif request_path.endswith(('.rss', '/feed')):
        style = FormatStyle.rss
        style = FormatStyle.rss

    # TODO: reconsider
    # if format_param := request.query_params.get('format'):
    #     if format_param == 'json':
    #         style = FormatStyle.json
    #     elif format_param == 'xml':
    #         style = FormatStyle.xml
    #     elif format_param == 'rss':
    #         style = FormatStyle.rss

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
