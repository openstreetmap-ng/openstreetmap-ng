import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import msgspec

from app.config import USER_AGENT

HTTP = httpx.AsyncClient(
    headers={'User-Agent': USER_AGENT},
    timeout=httpx.Timeout(connect=10, read=15, write=10, pool=10),
    follow_redirects=True,
    http1=True,
    http2=True,
)


def typed_msgpack_decoder(t: type | None) -> msgspec.msgpack.Decoder:
    """
    Create a MessagePack decoder which returns a specific type.
    """
    return msgspec.msgpack.Decoder(t) if (t is not None) else msgspec.msgpack.Decoder()


def typed_json_decoder(t: type | None) -> msgspec.json.Decoder:
    """
    Create a JSON decoder which returns a specific type.
    """
    return msgspec.json.Decoder(t) if (t is not None) else msgspec.json.Decoder()


MSGPACK_ENCODE = msgspec.msgpack.Encoder(decimal_format='number', uuid_format='bytes', order='sorted').encode
MSGPACK_DECODE = typed_msgpack_decoder(None).decode
JSON_ENCODE = msgspec.json.Encoder(decimal_format='number', order='sorted').encode
JSON_DECODE = typed_json_decoder(None).decode


# TODO: reporting of deleted accounts (prometheus)
# NOTE: breaking change


def unicode_normalize(text: str) -> str:
    """
    Normalize a string to NFC form.
    """
    return unicodedata.normalize('NFC', text)


def extend_query_params(uri: str, params: dict[str, str]) -> str:
    """
    Extend the query parameters of a URI.

    >>> extend_query_params('http://example.com', {'foo': 'bar'})
    'http://example.com?foo=bar'
    """
    if not params:
        return uri
    uri_ = urlsplit(uri)
    query = parse_qsl(uri_.query, keep_blank_values=True)
    query.extend(params.items())
    return urlunsplit(uri_._replace(query=urlencode(query)))
