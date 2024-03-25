from datetime import timedelta

from app.lib.date_utils import utcnow
from app.lib.jinja_env import stripspecial, timeago
from app.lib.translation import translation_context


def test_timeago():
    with translation_context('en'):
        assert timeago(utcnow() + timedelta(seconds=5)) == 'less than 1 second ago'
        assert timeago(utcnow() - timedelta(seconds=35)) == 'half a minute ago'
        assert timeago(utcnow() - timedelta(days=370)) == '1 year ago'


def test_stripspecial():
    assert stripspecial('Hello World!') == 'Hello World'
    assert stripspecial(', Hello') == 'Hello'
