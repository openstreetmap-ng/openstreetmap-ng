import ssl
import unicodedata
from functools import cache
from typing import Any, Unpack
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import certifi
import msgspec
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from aiohttp.client import _RequestContextManager, _RequestOptions

from app.config import USER_AGENT
from app.limits import DNS_CACHE_EXPIRE

JSON_ENCODE = msgspec.json.Encoder(decimal_format='number', order='sorted').encode
JSON_DECODE = msgspec.json.Decoder().decode


def json_encodes(obj: Any) -> str:
    """
    Like JSON_ENCODE, but returns a string.

    >>> json_encodes({'foo': 'bar'})
    '{"foo": "bar"}'
    """
    return JSON_ENCODE(obj).decode()


@cache
def _http() -> ClientSession:
    """
    Caching HTTP client factory.
    """
    return ClientSession(
        connector=TCPConnector(
            ssl=ssl.create_default_context(cafile=certifi.where()),
            ttl_dns_cache=int(DNS_CACHE_EXPIRE.total_seconds()),
        ),
        headers={'User-Agent': USER_AGENT},
        json_serialize=json_encodes,
        timeout=ClientTimeout(total=15, connect=10),
    )


def http_get(url: str, **kwargs: Unpack[_RequestOptions]) -> _RequestContextManager:
    """
    Perform a HTTP GET request.
    """
    return _http().get(url, **kwargs)


def http_post(url: str, **kwargs: Unpack[_RequestOptions]) -> _RequestContextManager:
    """
    Perform a HTTP POST request.
    """
    return _http().post(url, **kwargs)


# TODO: reporting of deleted accounts (prometheus)
# NOTE: breaking change


def unicode_normalize(text: str) -> str:
    """
    Normalize a string to NFC form.
    """
    return unicodedata.normalize('NFC', text)


def extend_query_params(uri: str, params: dict[str, str], *, fragment: bool = False) -> str:
    """
    Extend the query parameters of a URI.

    >>> extend_query_params('http://example.com', {'foo': 'bar'})
    'http://example.com?foo=bar'
    >>> extend_query_params('http://example.com', {'foo': 'bar'}, fragment=True)
    'http://example.com#foo=bar'
    """
    if not params:
        return uri
    uri_ = urlsplit(uri)
    if fragment:
        query = parse_qsl(uri_.fragment, keep_blank_values=True)
    else:
        query = parse_qsl(uri_.query, keep_blank_values=True)
    query.extend(params.items())
    query_str = urlencode(query)
    if fragment:
        uri_ = uri_._replace(fragment=query_str)
    else:
        uri_ = uri_._replace(query=query_str)
    return urlunsplit(uri_)


def splitlines_trim(s: str) -> list[str]:
    """
    Split a string by lines, trim whitespace from each line, and ignore empty lines.

    >>> splitlines_trim('foo\\n\\nbar\\n')
    ['foo', 'bar']
    """
    result: list[str] = []
    for line in s.splitlines():
        line = line.strip()
        if line:
            result.append(line)
    return result
