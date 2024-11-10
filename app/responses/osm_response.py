from collections.abc import Callable, Mapping, Sequence
from functools import wraps
from typing import Any, NoReturn, override

import cython
import orjson
from fastapi import APIRouter, Response
from fastapi.dependencies.utils import get_dependant
from fastapi.routing import APIRoute
from starlette.routing import request_response

from app.config import ATTRIBUTION_URL, COPYRIGHT, GENERATOR, LICENSE_URL
from app.lib.format_style_context import format_style
from app.lib.xmltodict import XMLToDict
from app.middlewares.request_context_middleware import get_request

_json_attributes = {
    'version': '0.6',
    'generator': GENERATOR,
    'copyright': COPYRIGHT,
    'attribution': ATTRIBUTION_URL,
    'license': LICENSE_URL,
}

_xml_attributes = {
    '@version': '0.6',
    '@generator': GENERATOR,
    '@copyright': COPYRIGHT,
    '@attribution': ATTRIBUTION_URL,
    '@license': LICENSE_URL,
}

_gpx_attributes = {
    '@version': '1.1',
    '@creator': GENERATOR,
    '@copyright': COPYRIGHT,
    '@attribution': ATTRIBUTION_URL,
    '@license': LICENSE_URL,
    '@xmlns': 'http://www.topografix.com/GPX/1/1',
    # XMLToDict does not support setting namespaces yet
    #'@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    #'@xsi:schemaLocation': 'http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd',
}


class OSMResponse(Response):
    xml_root = 'osm'

    @override
    def render(self, content) -> NoReturn:
        raise RuntimeError('Setup APIRouter with setup_api_router_response')

    @classmethod
    def serialize(cls, content: Any) -> Response:
        style = format_style()

        if style == 'json':
            # include json attributes if api 0.6 and not notes
            request_path: str = get_request().url.path
            if request_path.startswith('/api/0.6/') and not request_path.startswith('/api/0.6/notes'):
                if isinstance(content, Mapping):
                    content = {**_json_attributes, **content}
                else:
                    raise TypeError(f'Invalid json content type {type(content)}')

            encoded = orjson.dumps(content, option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_UTC_Z)
            return Response(encoded, media_type='application/json; charset=utf-8')

        elif style == 'xml':
            if isinstance(content, Mapping):
                content = {cls.xml_root: {**_xml_attributes, **content}}
            elif isinstance(content, Sequence) and not isinstance(content, str):
                content = {cls.xml_root: (*_xml_attributes.items(), *content)}
            else:
                raise TypeError(f'Invalid xml content type {type(content)}')

            encoded = XMLToDict.unparse(content, raw=True)
            return Response(encoded, media_type='application/xml; charset=utf-8')

        elif style == 'rss':
            if not isinstance(content, bytes):
                raise TypeError(f'Invalid rss content type {type(content)}')

            return Response(content, media_type='application/rss+xml; charset=utf-8')

        elif style == 'gpx':
            if isinstance(content, Mapping):
                content = {cls.xml_root: {**_gpx_attributes, **content}}
            elif isinstance(content, Sequence) and not isinstance(content, str):
                content = {cls.xml_root: (*_gpx_attributes.items(), *content)}
            else:
                raise TypeError(f'Invalid xml content type {type(content)}')

            encoded = XMLToDict.unparse(content, raw=True)
            return Response(encoded, media_type='application/gpx+xml; charset=utf-8')

        else:
            raise NotImplementedError(f'Unsupported osm format style {style!r}')


class OSMChangeResponse(OSMResponse):
    xml_root = 'osmChange'


class DiffResultResponse(OSMResponse):
    xml_root = 'diffResult'


class GPXResponse(OSMResponse):
    xml_root = 'gpx'


def setup_api_router_response(router: APIRouter) -> None:
    """
    Setup APIRouter to use optimized OSMResponse serialization.

    Default FastAPI serialization is slow and redundant.

    This is quite hacky as FastAPI does not expose an easy way to override it.
    """
    for route in router.routes:
        # override only supported endpoints
        if not isinstance(route, APIRoute):
            continue

        if isinstance(route.response_class, type) and issubclass(route.response_class, OSMResponse):
            response_class = route.response_class
        else:
            response_class = OSMResponse

        route.endpoint = _get_serializing_endpoint(route.endpoint, response_class)
        # fixup other fields:
        route.dependant = get_dependant(path=route.path_format, call=route.endpoint)
        route.app = request_response(route.get_route_handler())


@cython.cfunc
def _get_serializing_endpoint(endpoint: Callable, response_class: type[OSMResponse]):
    @wraps(endpoint)
    async def serializing_endpoint(*args, **kwargs):
        content = await endpoint(*args, **kwargs)

        # pass-through serialized response
        if isinstance(content, Response):
            return content

        return response_class.serialize(content)

    return serializing_endpoint
