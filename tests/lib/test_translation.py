from datetime import timedelta

import pytest

from app.config import DEFAULT_LANGUAGE
from app.lib.date_utils import utcnow
from app.lib.translation import (
    primary_translation_language,
    stripspecial,
    t,
    timeago,
    translation_context,
    translation_languages,
)


def test_translate_missing():
    with translation_context('pl'):
        assert t('missing_translation_key') == 'missing_translation_key'


def test_translate_local_chapters():
    with translation_context('en'):
        with translation_context('pl'):
            assert primary_translation_language() == 'pl'
            assert translation_languages() == ('pl', DEFAULT_LANGUAGE)
            assert t('osm_community_index.communities.OSM-PL-chapter.name') == 'OpenStreetMap Polska'

        assert primary_translation_language() == 'en'
        assert t('osm_community_index.communities.OSM-PL-chapter.name') == 'OpenStreetMap Poland'

    with pytest.raises(LookupError):
        t('osm_community_index.communities.OSM-PL-chapter.name')


def test_timeago():
    with translation_context('en'):
        assert timeago(utcnow() + timedelta(seconds=5)) == 'less than 1 second ago'
        assert timeago(utcnow() - timedelta(seconds=35)) == 'half a minute ago'
        assert timeago(utcnow() - timedelta(days=370)) == '1 year ago'


def test_stripspecial():
    assert stripspecial('Hello World!') == 'Hello World'
    assert stripspecial(', Hello') == 'Hello'
