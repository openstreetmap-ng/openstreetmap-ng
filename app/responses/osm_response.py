from collections.abc import Callable
from functools import wraps
from typing import Any, NoReturn, override

import cython
import orjson
from fastapi import APIRouter, Response
from fastapi.dependencies.utils import get_dependant
from fastapi.routing import APIRoute, request_response

from app.config import ATTRIBUTION_URL, COPYRIGHT, GENERATOR, LICENSE_URL
from app.lib.format_style_context import format_style
from app.lib.xmltodict import XMLToDict
from app.middlewares.request_context_middleware import get_request

_JSON_ATTRS = {
    'version': '0.6',
    'generator': GENERATOR,
    'copyright': COPYRIGHT,
    'attribution': ATTRIBUTION_URL,
    'license': LICENSE_URL,
}

_XML_ATTRS = {
    '@version': '0.6',
    '@generator': GENERATOR,
    '@copyright': COPYRIGHT,
    '@attribution': ATTRIBUTION_URL,
    '@license': LICENSE_URL,
}

_GPX_ATTRS = {
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
            return _serialize_json(content)
        if style == 'xml':
            return _serialize_xml(cls.xml_root, content)
        if style == 'rss':
            return _serialize_rss(content)
        if style == 'gpx':
            return _serialize_gpx(cls.xml_root, content)

        raise NotImplementedError(f'Unsupported osm format style {style!r}')


class OSMChangeResponse(OSMResponse):
    xml_root = 'osmChange'


class DiffResultResponse(OSMResponse):
    xml_root = 'diffResult'


class GPXResponse(OSMResponse):
    xml_root = 'gpx'


@cython.cfunc
def _serialize_json(content: Any):
    # include json attributes if api 0.6 and not notes
    path: str = get_request().url.path
    if path.startswith('/api/0.6/') and not path.startswith('/api/0.6/notes'):
        if not isinstance(content, dict):
            raise TypeError(f'Invalid json content type {type(content)}')
        content = {**_JSON_ATTRS, **content}

    encoded = orjson.dumps(
        content,
        option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_UTC_Z,
    )
    return Response(encoded, media_type='application/json; charset=utf-8')


@cython.cfunc
def _serialize_xml(xml_root: str, content: Any):
    if isinstance(content, dict):
        content = {xml_root: {**_XML_ATTRS, **content}}
    elif isinstance(content, (list, tuple)):  # noqa: UP038
        content = {xml_root: (*_XML_ATTRS.items(), *content)}
    else:
        raise TypeError(f'Invalid xml content type {type(content)}')

    encoded = XMLToDict.unparse(content, binary=True)
    return Response(encoded, media_type='application/xml; charset=utf-8')


@cython.cfunc
def _serialize_rss(content: Any):
    if not isinstance(content, bytes):
        raise TypeError(f'Invalid rss content type {type(content)}')

    return Response(content, media_type='application/rss+xml; charset=utf-8')


@cython.cfunc
def _serialize_gpx(xml_root: str, content: Any):
    if isinstance(content, dict):
        content = {xml_root: {**_GPX_ATTRS, **content}}
    elif isinstance(content, (list, tuple)):  # noqa: UP038
        content = {xml_root: (*_GPX_ATTRS.items(), *content)}
    else:
        raise TypeError(f'Invalid xml content type {type(content)}')

    encoded = XMLToDict.unparse(content, binary=True)
    return Response(encoded, media_type='application/gpx+xml; charset=utf-8')


def setup_api_router_response(router: APIRouter) -> None:
    """
    Setup APIRouter to use optimized OSMResponse serialization.
    Default FastAPI serialization is slow and redundant.
    This is quite hacky as FastAPI does not expose an easy way to override it.
    """
    for route in router.routes:
        # Overriding only supported endpoints
        if not isinstance(route, APIRoute):
            continue

        if (
            isinstance(route.response_class, type)  #
            and issubclass(route.response_class, OSMResponse)
        ):
            response_class = route.response_class
        else:
            response_class = OSMResponse

        route.endpoint = _get_serializing_endpoint(route.endpoint, response_class)
        # Also fixup other fields:
        route.dependant = get_dependant(path=route.path_format, call=route.endpoint)
        route.app = request_response(route.get_route_handler())


@cython.cfunc
def _get_serializing_endpoint(endpoint: Callable, response_class: type[OSMResponse]):
    @wraps(endpoint)
    async def serializing_endpoint(*args, **kwargs):
        content = await endpoint(*args, **kwargs)

        # Serialize responses only if needed
        return (
            content
            if isinstance(content, Response)
            else response_class.serialize(content)
        )

    return serializing_endpoint
