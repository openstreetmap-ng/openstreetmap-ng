import pytest

from app.config import DEFAULT_LANGUAGE
from app.lib.translation import (
    primary_translation_locale,
    t,
    translation_context,
    translation_locales,
)


def test_translation_missing_key():
    with translation_context('pl'):
        assert t('missing_translation_key') == 'missing_translation_key'


def test_translation_context():
    with translation_context('en'):
        with translation_context('pl'):
            assert primary_translation_locale() == 'pl'
            assert translation_locales() == ('pl', DEFAULT_LANGUAGE)
            assert t('osm_community_index.communities.OSM-PL-chapter.name') == 'OpenStreetMap Polska'

        assert primary_translation_locale() == 'en'
        assert t('osm_community_index.communities.OSM-PL-chapter.name') == 'OpenStreetMap Poland'


def test_translation_context_unknown():
    with translation_context('unknown'):
        assert translation_locales() == (DEFAULT_LANGUAGE,)


def test_translation_without_context():
    with pytest.raises(LookupError):
        t('osm_community_index.communities.OSM-PL-chapter.name')
