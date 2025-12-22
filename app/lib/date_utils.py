from datetime import UTC, date, datetime
from typing import overload

import cython
import dateutil.parser
import re2
from babel import Locale
from babel.core import UnknownLocaleError
from babel.dates import format_datetime

from app.config import LEGACY_HIGH_PRECISION_TIME
from app.lib.locale import DEFAULT_LOCALE
from app.lib.translation import primary_translation_locale
from app.models.types import LocaleCode

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
def _babel_locale(locale: LocaleCode, /, _CACHE: dict[str, Locale] = {}) -> Locale:
    if (cached := _CACHE.get(locale)) is not None:
        return cached

    try:
        parsed = Locale.parse(locale.replace('-', '_'))
    except (UnknownLocaleError, ValueError):
        parsed = Locale.parse(DEFAULT_LOCALE.replace('-', '_'))

    _CACHE[locale] = parsed
    return parsed


def format_rfc2822_date(dt: date | datetime, /) -> str:
    """Format a date/datetime similar to RFC2822, using the active translation locale."""
    if isinstance(dt, datetime):
        dt = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    else:
        dt = datetime(dt.year, dt.month, dt.day, tzinfo=UTC)

    locale = _babel_locale(primary_translation_locale())
    return format_datetime(dt, 'EEE, dd MMM yyyy HH:mm:ss Z', locale=locale)


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
