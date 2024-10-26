import pytest

from app.lib.tags_format import tags_format
from app.lib.translation import translation_context
from app.models.tags_format import ValueFormat
from app.models.types import LocaleCode


@pytest.mark.parametrize(
    ('tags', 'key', 'values'),
    [
        (
            # comment with potentially malicious content
            {'comment': 'https://example.com <script>'},
            ValueFormat('comment', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:comment'),
            [
                ValueFormat(
                    'https://example.com <script>',
                    'html',
                    '<p><a href="https://example.com" rel="noopener nofollow">https://example.com</a> &lt;script&gt;</p>',
                )
            ],
        ),
        (
            # colors
            {'colour': '#ff0000;invalid;AliceBlue'},
            ValueFormat('colour', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:colour'),
            [
                ValueFormat('#ff0000', 'color', '#ff0000'),
                ValueFormat('invalid'),
                ValueFormat('AliceBlue', 'color', 'AliceBlue'),
            ],
        ),
        (
            # emails
            {'email': 'support@openstreetmap.org;example@example.com'},
            ValueFormat('email', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:email'),
            [
                ValueFormat('support@openstreetmap.org', 'email', 'mailto:support@openstreetmap.org'),
                ValueFormat('example@example.com', 'email', 'mailto:example@example.com'),
            ],
        ),
        (
            # phones
            {'phone': '+1-234-567-8901;+7925805204786492'},
            ValueFormat('phone', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:phone'),
            [
                ValueFormat('+1-234-567-8901', 'phone', 'tel:+12345678901'),
                ValueFormat('+7925805204786492'),
            ],
        ),
        (
            # urls
            {'url': 'HTTPS://www.openstreetmap.org;ftp://www.openstreetmap.org'},
            ValueFormat('url', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:url'),
            [
                ValueFormat('HTTPS://www.openstreetmap.org', 'url', 'HTTPS://www.openstreetmap.org'),
                ValueFormat('ftp://www.openstreetmap.org'),
            ],
        ),
        (
            # wikipedia with fragment
            {'wikipedia': 'Test#abc'},
            ValueFormat('wikipedia', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:wikipedia'),
            [ValueFormat('Test#abc', 'url-safe', 'https://en.wikipedia.org/wiki/Test#abc')],
        ),
        (
            # regional wikipedia
            {'pl:wikipedia': 'Test'},
            ValueFormat('pl:wikipedia'),
            [ValueFormat('Test', 'url-safe', 'https://pl.wikipedia.org/wiki/Test')],
        ),
        (
            # wikidata id
            {'wikidata': 'q123'},
            ValueFormat('wikidata', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikidata'),
            [ValueFormat('q123', 'url-safe', 'https://www.wikidata.org/entity/q123')],
        ),
        (
            # commons file prefix
            {'wikimedia_commons': 'file:Test'},
            ValueFormat('wikimedia_commons', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons'),
            [ValueFormat('file:Test', 'url-safe', 'https://commons.wikimedia.org/wiki/file:Test')],
        ),
        (
            # commons category prefix
            {'wikimedia_commons': 'Category:Test'},
            ValueFormat('wikimedia_commons', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons'),
            [ValueFormat('Category:Test', 'url-safe', 'https://commons.wikimedia.org/wiki/Category:Test')],
        ),
        (
            # full osm wiki key/tag support
            {'amenity': 'bench'},
            ValueFormat('amenity', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:amenity'),
            [ValueFormat('bench', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Tag:amenity=bench')],
        ),
    ],
)
def test_tags_format(tags: dict[str, str], key: ValueFormat, values: list[ValueFormat]):
    with translation_context(LocaleCode('pl')):
        formatted = tags_format(tags)
        collection = next(iter(formatted.values()))
        assert key == collection.key
        assert values == collection.values
