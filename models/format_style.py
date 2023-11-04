from enum import StrEnum
from typing import Self


class FormatStyle(StrEnum):
    json = 'json'
    xml = 'xml'
    rss = 'rss'

    @classmethod
    def media_type(cls, style: Self) -> str:
        if style == cls.json:
            return 'application/json; charset=utf-8'
        elif style == cls.xml:
            return 'application/xml; charset=utf-8'
        elif style == cls.rss:
            return 'application/rss+xml; charset=utf-8'
        else:
            raise NotImplementedError(f'Unsupported format style {style!r}')
