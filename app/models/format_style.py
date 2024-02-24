from enum import Enum
from typing import Self


class FormatStyle(str, Enum):
    json = 'json'
    xml = 'xml'
    rss = 'rss'
    gpx = 'gpx'

    @classmethod
    def media_type(cls, style: Self) -> str:
        """
        Get the media type for the given format style.

        >>> FormatStyle.media_type(FormatStyle.json)
        'application/json; charset=utf-8'
        """

        if style == cls.json:
            return 'application/json; charset=utf-8'
        elif style == cls.xml:
            return 'application/xml; charset=utf-8'
        elif style == cls.rss:
            return 'application/rss+xml; charset=utf-8'
        elif style == cls.gpx:
            return 'application/gpx+xml; charset=utf-8'
        else:
            raise NotImplementedError(f'Unsupported format style {style!r}')
