import logging
import unicodedata
from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from shutil import which
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import dateutil.parser
import httpx
import msgspec
from fastapi import Request

from app.config import USER_AGENT


# TODO: configure logging
def _log_http_request(r: httpx.Request) -> None:
    logging.debug('Client HTTP request: %s %s', r.method, r.url)


def _log_http_response(r: httpx.Response) -> None:
    if r.is_success:
        logging.debug('Client HTTP response: %s %s %s', r.status_code, r.reason_phrase, r.url)
    else:
        logging.info('Client HTTP response: %s %s %s', r.status_code, r.reason_phrase, r.url)


HTTP = httpx.AsyncClient(
    headers={'User-Agent': USER_AGENT},
    timeout=httpx.Timeout(15),
    follow_redirects=True,
    http1=True,
    http2=True,
    # event_hooks={
    #     'request': [_log_http_request],
    #     'response': [_log_http_response],
    # },
)

MSGSPEC_MSGPACK_ENCODER = msgspec.msgpack.Encoder(decimal_format='number', uuid_format='bytes')
MSGSPEC_MSGPACK_DECODER = msgspec.msgpack.Decoder()
MSGSPEC_JSON_ENCODER = msgspec.json.Encoder(decimal_format='number')
MSGSPEC_JSON_DECODER = msgspec.json.Decoder()


# TODO: reporting of deleted accounts (prometheus)
# NOTE: breaking change


def unicode_normalize(text: str) -> str:
    """
    Normalize a string to NFC form.
    """

    return unicodedata.normalize('NFC', text)


def format_iso_date(date: datetime | None) -> str:
    """
    Format a datetime object as a string in ISO 8601 format.

    >>> format_date(datetime(2021, 12, 31, 15, 30, 45))
    '2021-12-31T15:30:45Z'
    """

    return date.strftime('%Y-%m-%dT%H:%M:%SZ') if date else 'None'


def format_sql_date(date: datetime | None) -> str:
    """
    Format a datetime object as a string in SQL format.

    >>> format_date(datetime(2021, 12, 31, 15, 30, 45))
    '2021-12-31 15:30:45 UTC'
    """

    return date.strftime('%Y-%m-%d %H:%M:%S UTC') if date else 'None'


def raise_if_program_unavailable(program: str) -> None:
    """
    Raise an exception if a program is not available.

    >>> raise_if_program_unavailable('bzip2')
    """

    if which(program) is None:
        raise FileNotFoundError(f'Program {program} is not available')


def extend_query_params(uri: str, params: dict) -> str:
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


def utcnow() -> datetime:
    """
    Return a datetime object representing the current time in UTC.
    """

    return datetime.now(UTC)


def parse_date(s: str) -> datetime:
    """
    Parse a string into a datetime object.

    Timezone information is ignored and the returned datetime object is always in UTC.

    >>> parse_date('2010-10-31')
    datetime.datetime(2010, 10, 31, 0, 0)
    """

    # TODO: support timezones
    date = dateutil.parser.parse(s, ignoretz=False)
    return date.replace(tzinfo=UTC) if date.tzinfo is None else date


def parse_request_ip(request: Request) -> IPv4Address | IPv6Address:
    """
    Parse the client IP address from a `Request`.
    """

    return ip_address(request.client.host)
