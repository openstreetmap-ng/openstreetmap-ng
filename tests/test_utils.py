from datetime import datetime, timedelta

import anyio
import pytest

from src.utils import (
    extend_query_params,
    format_iso_date,
    format_sql_date,
    parse_date,
    retry,
    unicode_normalize,
)

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        # already in NFC form
        ('naïve café', 'naïve café'),
        # NFD to NFC (diacritics separated)
        ('nai\u0308ve cafe\u0301', 'naïve café'),
        ('', ''),
    ],
)
def test_unicode_normalize(text, expected):
    assert unicode_normalize(text) == expected


@pytest.mark.parametrize(
    ('date', 'expected'),
    [
        (datetime(2021, 12, 31, 15, 30, 45), '2021-12-31T15:30:45Z'),
        (datetime(2021, 12, 31, 15, 30, 45, 123456), '2021-12-31T15:30:45Z'),
        (None, 'None'),
    ],
)
def test_format_iso_date(date, expected):
    assert format_iso_date(date) == expected


@pytest.mark.parametrize(
    ('date', 'expected'),
    [
        (datetime(2021, 12, 31, 15, 30, 45), '2021-12-31 15:30:45 UTC'),
        (datetime(2021, 12, 31, 15, 30, 45, 123456), '2021-12-31 15:30:45 UTC'),
        (None, 'None'),
    ],
)
def test_format_sql_date(date, expected):
    assert format_sql_date(date) == expected


async def test_retry():
    runs = 0

    @retry(None)
    async def func():
        nonlocal runs
        runs += 1

        # raise exception on first run
        if runs < 2:
            raise Exception

    await func()
    assert runs == 2


def test_retry_timeout():
    @retry(timedelta(seconds=1))
    async def func():
        raise RuntimeError

    pytest.raises(RuntimeError, anyio.run, func)


@pytest.mark.parametrize(
    ('uri', 'params', 'expected'),
    [
        ('http://example.com/', {}, 'http://example.com/'),
        ('http://example.com', {'key': 'value'}, 'http://example.com?key=value'),
        ('http://example.com/', {'key1': 'value1', 'key2': 'value2'}, 'http://example.com/?key1=value1&key2=value2'),
        ('http://example.com/?key1=value1', {'key2': 'value2'}, 'http://example.com/?key1=value1&key2=value2'),
        ('http://example.com/?key1=value1', {'key1': 'new_value1'}, 'http://example.com/?key1=value1&key1=new_value1'),
        (
            'http://example.com/',
            {'key with space': 'value with space'},
            'http://example.com/?key+with+space=value+with+space',
        ),
        (
            'http://example.com:8080/path;params?query#fragment',
            {'key': 'value'},
            'http://example.com:8080/path;params?query=&key=value#fragment',
        ),
    ],
)
def test_extend_query_params(uri, params, expected):
    assert extend_query_params(uri, params) == expected


@pytest.mark.parametrize(
    ('input', 'output'),
    [
        ('2010-10-31', datetime(2010, 10, 31)),
        ('2010-10-31T12:34:56Z', datetime(2010, 10, 31, 12, 34, 56)),
        ('2010-10-31T12:34:56.789Z', datetime(2010, 10, 31, 12, 34, 56, 789000)),
        ('2010-10-31T12:34:56+00:00', datetime(2010, 10, 31, 12, 34, 56)),
        ('Thu, 06 Oct 2011 02:26:12 UTC', datetime(2011, 10, 6, 2, 26, 12)),
        ('16:00', datetime.utcnow().replace(hour=16, minute=0, second=0, microsecond=0)),
        ('7/23', datetime.utcnow().replace(month=7, day=23, hour=0, minute=0, second=0, microsecond=0)),
        ('Aug 31', datetime.utcnow().replace(month=8, day=31, hour=0, minute=0, second=0, microsecond=0)),
        ('Aug 2000', datetime.utcnow().replace(month=8, year=2000, hour=0, minute=0, second=0, microsecond=0)),
    ],
)
def test_parse_date(input, output):
    assert parse_date(input) == output
