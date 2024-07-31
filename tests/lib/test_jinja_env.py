from datetime import timedelta

import pytest

from app.lib.date_utils import utcnow
from app.lib.jinja_env import stripspecial, timeago
from app.lib.translation import translation_context
from app.models.types import LocaleCode


@pytest.mark.parametrize(
    ('delta', 'expected'),
    [
        (timedelta(seconds=-5), 'less than 1 second ago'),
        (timedelta(seconds=35), 'half a minute ago'),
        (timedelta(days=370), '1 year ago'),
    ],
)
def test_timeago(delta, expected):
    with translation_context(LocaleCode('en')):
        assert timeago(utcnow() - delta) == expected


def test_timeago_never():
    with translation_context(LocaleCode('en')):
        assert timeago(None) == 'Never'


@pytest.mark.parametrize(
    ('input', 'expected'),
    [
        ('Hello World!', 'Hello World'),
        (', Hello', 'Hello'),
    ],
)
def test_stripspecial(input, expected):
    assert stripspecial(input) == expected
