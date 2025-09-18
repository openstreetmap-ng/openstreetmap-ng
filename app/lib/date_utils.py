from datetime import UTC, date, datetime
from typing import overload

import arrow
import cython
import dateutil.parser

from app.config import LEGACY_HIGH_PRECISION_TIME
from app.lib.translation import primary_translation_locale


@overload
def legacy_date(dt: None, /) -> None: ...
@overload
def legacy_date(dt: datetime, /) -> datetime: ...
def legacy_date(dt: datetime | None, /) -> datetime | None:
    """
    Convert date to legacy format (strip microseconds).

    >>> legacy_date(datetime(2021, 12, 31, 15, 30, 45, 123456))
    datetime.datetime(2021, 12, 31, 15, 30, 45)
    """
    return dt if dt is None or LEGACY_HIGH_PRECISION_TIME else dt.replace(microsecond=0)


def format_sql_date(dt: datetime | None, /) -> str:
    """
    Format a datetime object as a string in SQL format.

    >>> format_sql_date(datetime(2021, 12, 31, 15, 30, 45))
    '2021-12-31 15:30:45 UTC'
    """
    if dt is None:
        return 'None'
    tzinfo = dt.tzinfo
    assert tzinfo is None or tzinfo is UTC, f'Timezone must be UTC, got {tzinfo!r}'
    return dt.strftime(
        '%Y-%m-%d %H:%M:%S UTC' if not dt.microsecond else '%Y-%m-%d %H:%M:%S.%f UTC'
    )


@cython.cfunc
def _format_with_locale(dt: date | datetime, fmt: str, /) -> str:
    date_ = arrow.get(dt)
    try:
        return date_.format(fmt, locale=primary_translation_locale())
    except ValueError:
        return date_.format(fmt)


def format_rfc2822_date(dt: date | datetime, /) -> str:
    """Format a datetime object as an RFC2822 date string."""
    return _format_with_locale(dt, 'ddd, DD MMM YYYY HH:mm:ss Z')


def format_short_date(dt: date | datetime, /) -> str:
    """Format a datetime object as a short date string (MMMM D, YYYY)."""
    return _format_with_locale(dt, 'MMMM D, YYYY')


def get_month_name(dt: date | datetime, /, *, short: bool) -> str:
    """Get the name of the month of a datetime object."""
    return _format_with_locale(dt, 'MMM' if short else 'MMMM')


def get_weekday_name(dt: date | datetime, /, *, short: bool) -> str:
    """Get the name of the weekday of a datetime object."""
    return _format_with_locale(dt, 'ddd' if short else 'dddd')


def utcnow() -> datetime:
    """Return a datetime object representing the current time in UTC."""
    return datetime.now(UTC)


def parse_date(s: str, /) -> datetime:
    """
    Parse a string into a datetime object.
    Timezone information is ignored and the returned datetime object is always in UTC.

    >>> parse_date('2010-10-31')
    datetime.datetime(2010, 10, 31, 0, 0)
    """
    dt = dateutil.parser.parse(s, ignoretz=False)

    # Set or convert to UTC timezone
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
