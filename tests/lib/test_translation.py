from datetime import timedelta

import pytest

from app.config import DEFAULT_LANGUAGE
from app.lib.date_utils import utcnow
from app.lib.translation import primary_translation_language, timeago, translation_context, translation_languages


def test_translation_languages():
    with translation_context(['pl']):
        assert translation_languages() == ('pl', DEFAULT_LANGUAGE)


def test_primary_translation_language():
    with translation_context(['pl']):
        assert primary_translation_language() == 'pl'


@pytest.mark.parametrize(
    ('delta', 'output'),
    [
        (timedelta(seconds=-5), 'less than 1 second ago'),
        (timedelta(seconds=35), 'half a minute ago'),
        (timedelta(days=370), '1 year ago'),
    ],
)
def test_timeago(delta, output):
    with translation_context(['en']):
        now = utcnow() - delta
        assert timeago(now) == output
