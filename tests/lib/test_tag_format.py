import pytest

from app.lib.tag_format import TagFormatTuple, tag_format
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
            '#ff0000;invalid;aliceblue',
            (
                TagFormatTuple(TagFormat.color, '#ff0000', '#ff0000'),
                TagFormatTuple(TagFormat.default, 'invalid', 'invalid'),
                TagFormatTuple(TagFormat.color, 'aliceblue', 'aliceblue'),
            ),
        ),
        (
            '#ff00001; #ff0000',
            (
                TagFormatTuple(TagFormat.default, '#ff00001', '#ff00001'),
                TagFormatTuple(TagFormat.default, ' #ff0000', ' #ff0000'),
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
                TagFormatTuple(TagFormat.email, 'support@openstreetmap.org', 'mailto:support@openstreetmap.org'),
                TagFormatTuple(TagFormat.email, 'example@example.com', 'mailto:example@example.com'),
            ),
        ),
        (
            'invalid email address',
            (TagFormatTuple(TagFormat.default, 'invalid email address', 'invalid email address'),),
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
                TagFormatTuple(TagFormat.phone, '+1-234-567-8901', 'tel:+12345678901'),
                TagFormatTuple(TagFormat.default, '+7925805204786492', '+7925805204786492'),
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
                TagFormatTuple(TagFormat.url, 'https://www.openstreetmap.org', 'https://www.openstreetmap.org'),
                TagFormatTuple(TagFormat.default, 'ftp://www.openstreetmap.org', 'ftp://www.openstreetmap.org'),
            ),
        )
    ],
)
def test_tag_format_url(value, output):
    assert tag_format('url', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'Test',
            (TagFormatTuple(TagFormat.url, 'Test', 'https://en.wikipedia.org/wiki/Test?uselang=pl'),),
        ),
        (
            'Test#abc',
            (TagFormatTuple(TagFormat.url, 'Test#abc', 'https://en.wikipedia.org/wiki/Test?uselang=pl#abc'),),
        ),
    ],
)
def test_tag_format_wikipedia(value, output):
    with translation_context(['pl']):
        assert tag_format('wikipedia', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'Test',
            (TagFormatTuple(TagFormat.url, 'Test', 'https://pl.wikipedia.org/wiki/Test?uselang=pl'),),
        ),
    ],
)
def test_tag_format_wikipedia_lang(value, output):
    with translation_context(['pl']):
        assert tag_format('pl:wikipedia', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'Q123',
            (TagFormatTuple(TagFormat.url, 'Q123', 'https://www.wikidata.org/entity/Q123?uselang=pl'),),
        ),
        (
            'q123',
            (TagFormatTuple(TagFormat.default, 'q123', 'q123'),),
        ),
    ],
)
def test_tag_format_wikidata(value, output):
    with translation_context(['pl']):
        assert tag_format('wikidata', value) == output


@pytest.mark.parametrize(
    ('value', 'output'),
    [
        (
            'File:Test',
            (TagFormatTuple(TagFormat.url, 'File:Test', 'https://commons.wikimedia.org/wiki/File:Test?uselang=pl'),),
        ),
        (
            'file:Test',
            (TagFormatTuple(TagFormat.default, 'file:Test', 'file:Test'),),
        ),
        (
            'Category:Test',
            (
                TagFormatTuple(
                    TagFormat.url, 'Category:Test', 'https://commons.wikimedia.org/wiki/Category:Test?uselang=pl'
                ),
            ),
        ),
    ],
)
def test_tag_format_wikimedia_commons(value, output):
    with translation_context(['pl']):
        assert tag_format('wikimedia_commons', value) == output
