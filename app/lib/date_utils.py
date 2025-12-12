from datetime import UTC, date, datetime
from typing import overload

import arrow
import cython
import dateutil.parser
import re2

from app.config import LEGACY_HIGH_PRECISION_TIME
from app.lib.translation import primary_translation_locale

# ISO-ish datetime gate for the fast path in parse_date().
# We intentionally keep this conservative: if a string doesn't look like ISO 8601,
# fall back to dateutil (supports RFC2822, partial dates like "Aug 31", times like "16:00", etc.).
_ISO_LIKE_RE = re2.compile(
    r'^\d{4}-\d{2}-\d{2}'
    r'(?:[T ]\d{2}:\d{2}:\d{2}'
    r'(?:\.\d{1,9})?'
    r'(?:Z|[+-]\d{2}:?\d{2})?'
    r')?$'
)

# datetime.fromisoformat() only supports up to 6 fractional digits (microseconds).
# If input has more (e.g., nanoseconds), truncate instead of failing.
# Example: ".123456789Z" -> ".123456Z"
_ISO_FRACTION_TRUNC_RE = re2.compile(r'\.(\d{6})\d+')


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
    s = s.strip()

    # dateutil.parser.parse is flexible but slow.
    # Fast-path ISO-like strings via datetime.fromisoformat
    if _ISO_LIKE_RE.fullmatch(s):
        s2 = _ISO_FRACTION_TRUNC_RE.sub(r'.\1', s)
        try:
            dt = datetime.fromisoformat(s2)
        except ValueError:
            dt = dateutil.parser.parse(s, ignoretz=False)
    else:
        dt = dateutil.parser.parse(s, ignoretz=False)

    # Set or convert to UTC timezone
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
