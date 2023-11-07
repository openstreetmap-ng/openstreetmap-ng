import functools
import logging
import math
import random
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Callable, Self
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import anyio
import dateutil.parser
import httpx
from shapely.geometry import Point

from config import USER_AGENT

_EARTH_RADIUS_METERS = 6371000


def _log_http_request(r: httpx.Request) -> None:
    logging.debug(
        'Client HTTP request: %s %s',
        r.method,
        r.url)


def _log_http_response(r: httpx.Response) -> None:
    if r.is_success:
        logging.debug(
            'Client HTTP response: %s %s %s',
            r.status_code,
            r.reason_phrase,
            r.url)
    else:
        logging.info(
            'Client HTTP response: %s %s %s',
            r.status_code,
            r.reason_phrase,
            r.url)


HTTP = httpx.AsyncClient(
    headers={'User-Agent': USER_AGENT},
    timeout=httpx.Timeout(15),
    follow_redirects=True,
    http1=True,
    http2=True,
    event_hooks={
        'request': [_log_http_request],
        'response': [_log_http_response],
    }
)

# TODO: reporting of deleted accounts

# NOTE: breaking change


def unicode_normalize(text: str) -> str:
    '''
    Normalize a string to NFC form.
    '''

    return unicodedata.normalize('NFC', text)


def format_iso_date(date: datetime | None) -> str:
    '''
    Format a datetime object as a string in ISO 8601 format.

    >>> format_date(datetime(2021, 12, 31, 15, 30, 45))
    '2021-12-31T15:30:45Z'
    '''

    return date.strftime('%Y-%m-%dT%H:%M:%SZ') if date else 'None'


def format_sql_date(date: datetime | None) -> str:
    '''
    Format a datetime object as a string in SQL format.

    >>> format_date(datetime(2021, 12, 31, 15, 30, 45))
    '2021-12-31 15:30:45 UTC'
    '''

    return date.strftime('%Y-%m-%d %H:%M:%S UTC') if date else 'None'


def meters_to_radians(meters: float) -> float:
    return meters / _EARTH_RADIUS_METERS


def radians_to_meters(radians: float) -> float:
    return radians * _EARTH_RADIUS_METERS


def haversine_distance(p1: Point, p2: Point) -> float:
    '''
    Calculate the distance between two points on the Earth's surface using the Haversine formula.

    Returns the distance in meters.
    '''

    lon1, lat1 = p1.x, p1.y
    lon2, lat2 = p2.x, p2.y

    dlon = math.radians(lon2 - lon1)
    dlat = math.radians(lat2 - lat1)

    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return c * _EARTH_RADIUS_METERS


def retry(timeout: timedelta | None, *, start: float = 1, limit: float = 300):
    if timeout is None:
        timeout_seconds = math.inf
    else:
        timeout_seconds = timeout.total_seconds()

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            ts = time.perf_counter()
            sleep = start

            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logging.info(f'Function {func.__qualname__} failed, retrying...', exc_info=True)
                    if (time.perf_counter() + sleep) - ts > timeout_seconds:
                        raise e
                    await anyio.sleep(sleep)
                    sleep = min(sleep * (1.5 + random.random()), limit)

        return wrapper
    return decorator


def updating_cached_property(compare: Callable[[Self], Any]) -> property:
    def decorator(func):
        cache = None

        @property
        @functools.wraps(func)
        def wrapper(self: Self):
            nonlocal cache
            if cache is None or cache != compare(self):
                cache = func(self)
            return cache
        return wrapper
    return decorator


def extend_query_params(uri: str, params: dict) -> str:
    '''
    Extend the query parameters of a URI.

    >>> extend_query_params('http://example.com', {'foo': 'bar'})
    'http://example.com?foo=bar'
    '''

    if not params:
        return uri

    uri_ = urlparse(uri)
    query = parse_qsl(uri_.query, keep_blank_values=True)
    query.extend(params.items())
    return urlunparse(uri_._replace(query=urlencode(query)))


def utcnow() -> datetime:
    '''
    Return a datetime object representing the current time in UTC.
    '''

    return datetime.utcnow()


def parse_date(s: str) -> datetime:
    '''
    Parse a string into a datetime object.

    Timezone information is ignored and the returned datetime object is always in UTC.

    >>> parse_date('2010-10-31')
    datetime.datetime(2010, 10, 31, 0, 0)
    '''

    # TODO: support timezones
    return dateutil.parser.parse(s, ignoretz=True)
