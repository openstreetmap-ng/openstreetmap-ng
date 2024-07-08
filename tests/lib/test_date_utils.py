from datetime import UTC, datetime

import pytest
from dateutil.tz import tzoffset

from app.lib.date_utils import format_rfc2822_date, format_sql_date, parse_date, utcnow


@pytest.mark.parametrize(
    ('input', 'expected'),
    [
        (datetime(2021, 12, 31, 15, 30, 45), '2021-12-31 15:30:45 UTC'),  # noqa: DTZ001
        (datetime(2021, 12, 31, 15, 30, 45, 123456, UTC), '2021-12-31 15:30:45.123456 UTC'),
        (None, 'None'),
    ],
)
def test_format_sql_date(input, expected):
    assert format_sql_date(input) == expected


def test_format_sql_date_non_utc():
    with pytest.raises(AssertionError):
        format_sql_date(datetime(2021, 12, 31, 15, 30, 45, tzinfo=tzoffset(None, 32400)))


def test_format_rfc2822_date():
    assert format_rfc2822_date(datetime(2021, 12, 31, 15, 30, 45, tzinfo=UTC)) == 'Fri, 31 Dec 2021 15:30:45 +0000'


def test_utcnow():
    assert utcnow().tzinfo is UTC


@pytest.mark.parametrize(
    ('input', 'expected'),
    [
        ('2010-10-31', datetime(2010, 10, 31, tzinfo=UTC)),
        ('2010-10-31T12:34:56', datetime(2010, 10, 31, 12, 34, 56, 0, UTC)),
        ('2010-10-31T12:34:56.789Z', datetime(2010, 10, 31, 12, 34, 56, 789000, UTC)),
        ('2010-10-31T12:34:56+00:00', datetime(2010, 10, 31, 12, 34, 56, 0, UTC)),
        ('2010-10-31T12:34:56+01:00', datetime(2010, 10, 31, 11, 34, 56, 0, UTC)),
        ('Thu, 06 Oct 2011 02:26:12 UTC', datetime(2011, 10, 6, 2, 26, 12, 0, UTC)),
        ('16:00', utcnow().replace(hour=16, minute=0, second=0, microsecond=0)),
        ('7/23', utcnow().replace(month=7, day=23, hour=0, minute=0, second=0, microsecond=0)),
        ('Aug 31', utcnow().replace(month=8, day=31, hour=0, minute=0, second=0, microsecond=0)),
        ('Aug 2000', utcnow().replace(month=8, year=2000, hour=0, minute=0, second=0, microsecond=0)),
    ],
)
def test_parse_date(input, expected):
    assert parse_date(input) == expected
