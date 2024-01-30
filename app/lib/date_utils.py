from datetime import UTC, datetime

import dateutil.parser


def format_iso_date(date: datetime | None) -> str:
    """
    Format a datetime object as a string in ISO 8601 format.

    >>> format_date(datetime(2021, 12, 31, 15, 30, 45))
    '2021-12-31T15:30:45Z'
    """

    if date is None:
        return 'None'

    return date.strftime('%Y-%m-%dT%H:%M:%SZ')


def format_sql_date(date: datetime | None) -> str:
    """
    Format a datetime object as a string in SQL format.

    >>> format_date(datetime(2021, 12, 31, 15, 30, 45))
    '2021-12-31 15:30:45 UTC'
    """

    if date is None:
        return 'None'

    return date.strftime('%Y-%m-%d %H:%M:%S UTC')


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

    # ensure timezone is set
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)

    return date
