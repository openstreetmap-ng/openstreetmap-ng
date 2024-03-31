from datetime import UTC, datetime

import pytest
from dateutil.tz import tzoffset

from app.lib.date_utils import format_sql_date, parse_date


def test_format_sql_date():
    assert format_sql_date(datetime(2021, 12, 31, 15, 30, 45)) == '2021-12-31 15:30:45 UTC'
    assert format_sql_date(datetime(2021, 12, 31, 15, 30, 45, 123456, UTC)) == '2021-12-31 15:30:45.123456 UTC'
    assert format_sql_date(None) == 'None'

    with pytest.raises(AssertionError):
        format_sql_date(datetime(2021, 12, 31, 15, 30, 45, tzinfo=tzoffset(None, 32400)))


@pytest.mark.parametrize(
    ('input', 'output'),
    [
        ('2010-10-31', datetime(2010, 10, 31, tzinfo=UTC)),
        ('2010-10-31T12:34:56Z', datetime(2010, 10, 31, 12, 34, 56, tzinfo=UTC)),
        ('2010-10-31T12:34:56.789Z', datetime(2010, 10, 31, 12, 34, 56, 789000, tzinfo=UTC)),
        ('2010-10-31T12:34:56+00:00', datetime(2010, 10, 31, 12, 34, 56, tzinfo=UTC)),
        ('Thu, 06 Oct 2011 02:26:12 UTC', datetime(2011, 10, 6, 2, 26, 12, tzinfo=UTC)),
        ('16:00', datetime.now(UTC).replace(hour=16, minute=0, second=0, microsecond=0)),
        ('7/23', datetime.now(UTC).replace(month=7, day=23, hour=0, minute=0, second=0, microsecond=0)),
        ('Aug 31', datetime.now(UTC).replace(month=8, day=31, hour=0, minute=0, second=0, microsecond=0)),
        ('Aug 2000', datetime.now(UTC).replace(month=8, year=2000, hour=0, minute=0, second=0, microsecond=0)),
    ],
)
def test_parse_date(input, output):
    assert parse_date(input) == output
