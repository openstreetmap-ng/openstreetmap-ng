from abc import ABC
from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import Request

from models.format_style import FormatStyle


# TODO: middleware
# TODO: 0.7 only &format
class Format(ABC):
    _context = ContextVar('Format_context')

    @classmethod
    @contextmanager
    def style_context(cls, request: Request):
        # path defaults
        if request.url.path.startswith('/api/0.7/'):
            style = FormatStyle.json
        elif request.url.path.startswith('/api/'):
            style = FormatStyle.xml
        else:
            style = FormatStyle.json

        # overrides
        if request.url.path.endswith('.json'):
            style = FormatStyle.json
        elif request.url.path.endswith('.xml'):
            style = FormatStyle.xml
        elif request.url.path.endswith('.rss'):
            style = FormatStyle.rss
        else:
            if format := request.query_params.get('format'):
                if format == 'json':
                    style = FormatStyle.json
                elif format == 'xml':
                    style = FormatStyle.xml
                elif format == 'rss':
                    style = FormatStyle.rss

        token = cls._context.set(style)
        try:
            yield
        finally:
            cls._context.reset(token)

    @classmethod
    def style(cls) -> FormatStyle:
        return cls._context.get()

    @classmethod
    def is_json(cls) -> bool:
        return cls._context.get() == FormatStyle.json

    @classmethod
    def is_xml(cls) -> bool:
        return cls._context.get() == FormatStyle.xml

    @classmethod
    def is_rss(cls) -> bool:
        return cls._context.get() == FormatStyle.rss
