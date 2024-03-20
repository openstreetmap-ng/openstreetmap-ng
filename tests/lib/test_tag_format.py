import pytest

from app.lib.tag_format import TagFormatted, tag_format
from app.lib.translation import translation_context
from app.models.tag_format import TagFormat


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            '',
            (),
        ),
        (
            '#ff0000;invalid;AliceBlue',
            (
                TagFormatted(TagFormat.color, '#ff0000', '#ff0000'),
                TagFormatted(TagFormat.default, 'invalid', 'invalid'),
                TagFormatted(TagFormat.color, 'AliceBlue', 'AliceBlue'),
            ),
        ),
        (
            '#ff00001; #ff0000',
            (
                TagFormatted(TagFormat.default, '#ff00001', '#ff00001'),
                TagFormatted(TagFormat.default, ' #ff0000', ' #ff0000'),
            ),
        ),
    ],
)
def test_tag_format_colour(value, output):
    assert tag_format('colour', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'support@openstreetmap.org;example@example.com',
            (
                TagFormatted(TagFormat.email, 'support@openstreetmap.org', 'mailto:support@openstreetmap.org'),
                TagFormatted(TagFormat.email, 'example@example.com', 'mailto:example@example.com'),
            ),
        ),
        (
            'invalid email address',
            (TagFormatted(TagFormat.default, 'invalid email address', 'invalid email address'),),
        ),
    ],
)
def test_tag_format_email(value, output):
    assert tag_format('email', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            '+1-234-567-8901;+7925805204786492',
            (
                TagFormatted(TagFormat.phone, '+1-234-567-8901', 'tel:+12345678901'),
                TagFormatted(TagFormat.default, '+7925805204786492', '+7925805204786492'),
            ),
        )
    ],
)
def test_tag_format_phone(value, output):
    assert tag_format('phone', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'https://www.openstreetmap.org;ftp://www.openstreetmap.org',
            (
                TagFormatted(TagFormat.url, 'https://www.openstreetmap.org', 'https://www.openstreetmap.org'),
                TagFormatted(TagFormat.default, 'ftp://www.openstreetmap.org', 'ftp://www.openstreetmap.org'),
            ),
        ),
        (
            'HTTPS://WWW.OSM.ORG',
            (TagFormatted(TagFormat.url, 'HTTPS://WWW.OSM.ORG', 'HTTPS://WWW.OSM.ORG'),),
        ),
    ],
)
def test_tag_format_url(value, output):
    assert tag_format('url', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'Test',
            (TagFormatted(TagFormat.url, 'Test', 'https://en.wikipedia.org/wiki/Test?uselang=pl'),),
        ),
        (
            'Test#abc',
            (TagFormatted(TagFormat.url, 'Test#abc', 'https://en.wikipedia.org/wiki/Test?uselang=pl#abc'),),
        ),
    ],
)
def test_tag_format_wikipedia(value, output):
    with translation_context('pl'):
        assert tag_format('wikipedia', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'Test',
            (TagFormatted(TagFormat.url, 'Test', 'https://pl.wikipedia.org/wiki/Test?uselang=pl'),),
        ),
    ],
)
def test_tag_format_wikipedia_lang(value, output):
    with translation_context('pl'):
        assert tag_format('pl:wikipedia', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'Q123',
            (TagFormatted(TagFormat.url, 'Q123', 'https://www.wikidata.org/entity/Q123?uselang=pl'),),
        ),
        (
            'q123',
            (TagFormatted(TagFormat.url, 'q123', 'https://www.wikidata.org/entity/q123?uselang=pl'),),
        ),
    ],
)
def test_tag_format_wikidata(value, output):
    with translation_context('pl'):
        assert tag_format('wikidata', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'File:Test',
            (TagFormatted(TagFormat.url, 'File:Test', 'https://commons.wikimedia.org/wiki/File:Test?uselang=pl'),),
        ),
        (
            'file:Test',
            (TagFormatted(TagFormat.url, 'file:Test', 'https://commons.wikimedia.org/wiki/file:Test?uselang=pl'),),
        ),
        (
            'Category:Test',
            (
                TagFormatted(
                    TagFormat.url, 'Category:Test', 'https://commons.wikimedia.org/wiki/Category:Test?uselang=pl'
                ),
            ),
        ),
    ],
)
def test_tag_format_wikimedia_commons(value, output):
    with translation_context('pl'):
        assert tag_format('wikimedia_commons', value) == output
