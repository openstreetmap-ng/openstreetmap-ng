import functools
import logging
import math
import random
import time
import unicodedata
from collections.abc import Callable
from datetime import datetime, timedelta
from itertools import count
from typing import Any, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import anyio
import dateutil.parser
import httpx

from config import USER_AGENT
from limits import NG_MIGRATION_DATE


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
    event_hooks={
        'request': [_log_http_request],
        'response': [_log_http_response],
    },
)

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


def retry(timeout: timedelta | None, *, sleep_init: float = 1, sleep_limit: float = 300):
    """
    Decorator to retry a function.

    The function is retried until it succeeds or the timeout is reached.
    """

    timeout_seconds = math.inf if timeout is None else timeout.total_seconds()

    def decorator(func):
        async def wrapper(*args, **kwargs):
            ts = time.monotonic()
            sleep = sleep_init

            for attempt in count(1):
                try:
                    return await func(*args, **kwargs)
                except Exception:
                    next_timeout_seconds = (time.monotonic() + sleep) - ts

                    # retry is still possible
                    if next_timeout_seconds < timeout_seconds:
                        logging.info(
                            'Function %s failed at attempt %d, retrying in %.3f seconds',
                            func.__qualname__,
                            attempt,
                            sleep,
                            exc_info=True,
                        )
                        await anyio.sleep(sleep)
                        sleep = min(sleep * (1.5 + random.random()), sleep_limit)  # noqa: S311

                    # retry is not possible, re-raise the exception
                    else:
                        logging.warning(
                            'Function %s failed and timed out after %d attempts',
                            func.__qualname__,
                            attempt,
                            exc_info=True,
                        )
                        raise

        return wrapper

    return decorator


def updating_cached_property(compare: Callable[[Self], Any]) -> property:
    """
    A decorator to cache the result of a property with an auto-update condition.

    If compare returns a modified value, the property is re-evaluated.
    """

    # TODO: this is bad: singleton for all instances
    def decorator(func):
        cache = None
        compare_val = None

        @property
        @functools.wraps(func)
        def wrapper(self):
            nonlocal cache, compare_val
            new_compare_val = compare(self)
            if cache is None or compare_val != new_compare_val:
                cache = func(self)
                compare_val = new_compare_val
            return cache

        return wrapper

    return decorator


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

    return datetime.utcnow()


def parse_date(s: str) -> datetime:
    """
    Parse a string into a datetime object.

    Timezone information is ignored and the returned datetime object is always in UTC.

    >>> parse_date('2010-10-31')
    datetime.datetime(2010, 10, 31, 0, 0)
    """

    # TODO: support timezones
    return dateutil.parser.parse(s, ignoretz=True)


def is_migrated(date: datetime | None = None) -> bool:
    """
    Check if a date is after the migration to NextGen.

    This method is used to determine whether to enforce new validation limits.
    """

    if not date:
        date = utcnow()
    return date > NG_MIGRATION_DATE
