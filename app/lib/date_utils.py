from datetime import UTC, datetime
from email import utils
from typing import overload

import dateutil.parser

from app.config import LEGACY_HIGH_PRECISION_TIME


@overload
def legacy_date(date: None) -> None: ...


@overload
def legacy_date(date: datetime) -> datetime: ...


def legacy_date(date: datetime | None) -> datetime | None:
    """
    Convert date to legacy format (strip microseconds).

    >>> legacy_date(datetime(2021, 12, 31, 15, 30, 45, 123456))
    datetime.datetime(2021, 12, 31, 15, 30, 45)
    """
    if date is None:
        return date
    if LEGACY_HIGH_PRECISION_TIME:
        return date
    return date.replace(microsecond=0)


def format_sql_date(date: datetime | None) -> str:
    """
    Format a datetime object as a string in SQL format.

    >>> format_date(datetime(2021, 12, 31, 15, 30, 45))
    '2021-12-31 15:30:45 UTC'
    """
    if date is None:
        return 'None'
    tzinfo = date.tzinfo
    if tzinfo is not None and tzinfo is not UTC:
        raise AssertionError(f'Timezone must be UTC, got {tzinfo!r}')
    format = '%Y-%m-%d %H:%M:%S UTC' if date.microsecond == 0 else '%Y-%m-%d %H:%M:%S.%f UTC'
    return date.strftime(format)


def format_rfc2822_date(date: datetime) -> str:
    """
    Format a datetime object as an RFC2822 date string.
    """
    return utils.format_datetime(date)


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
    date = dateutil.parser.parse(s, ignoretz=False)

    if date.tzinfo is None:
        # attach UTC timezone if missing
        return date.replace(tzinfo=UTC)
    else:
        # convert to UTC timezone
        return date.astimezone(UTC)
