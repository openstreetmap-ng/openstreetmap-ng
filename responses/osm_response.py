import typing
from itertools import chain

import orjson
from fastapi import Response

from config import ATTRIBUTION_URL, COPYRIGHT, GENERATOR, LICENSE_URL
from lib.format import Format
from lib.xmltodict import XMLToDict
from models.format_style import FormatStyle


class OSMResponse(Response):
    xml_root = 'osm'

    def render(self, content: typing.Any) -> bytes:
        format_style = Format.style()
        self.media_type = FormatStyle.media_type(format_style)

        if format_style == Format.json:
            attributes = {
                'version': '0.6',  # TODO: 0.7 json generator
                'generator': GENERATOR,
                'copyright': COPYRIGHT,
                'attribution': ATTRIBUTION_URL,
                'license': LICENSE_URL,
            }

            if isinstance(content, dict):
                content |= attributes
            else:
                raise ValueError(f'Invalid content type {type(content)}')

            return orjson.dumps(content, option=orjson.OPT_NAIVE_UTC | orjson.OPT_UTC_Z)

        elif format_style == Format.xml:
            attributes = {
                '@version': '0.6',  # TODO: 0.7 xml generator
                '@generator': GENERATOR,
                '@copyright': COPYRIGHT,
                '@attribution': ATTRIBUTION_URL,
                '@license': LICENSE_URL,
            }

            if isinstance(content, dict):
                content = {self.xml_root: attributes | content}
            elif isinstance(content, (list, tuple)):
                content = {self.xml_root: tuple(chain(attributes.items(), content))}
            else:
                raise ValueError(f'Invalid content type {type(content)}')

            return XMLToDict.unparse(content, raw=True)

        else:
            # TODO: rss
            raise NotImplementedError(f'Unsupported format style {format_style!r}')


class OSMChangeResponse(OSMResponse):
    xml_root = 'osmChange'


class DiffResultResponse(OSMResponse):
    xml_root = 'diffResult'


class GPXResponse(OSMResponse):
    xml_root = 'gpx'
