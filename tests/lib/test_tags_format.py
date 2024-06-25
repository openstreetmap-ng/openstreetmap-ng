from collections.abc import Sequence

import pytest

from app.lib.tags_format import tags_format
from app.lib.translation import translation_context
from app.models.tag_format import TagFormat


@pytest.mark.parametrize(
    ('tags', 'key', 'vals'),
    [
        (
            # comment with potentially malicious content
            {'comment': 'https://example.com <script>'},
            TagFormat('comment', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:comment'),
            [
                TagFormat(
                    'https://example.com <script>',
                    'html',
                    '<a href="https://example.com" rel="nofollow">https://example.com</a> &lt;script&gt;',
                )
            ],
        ),
        (
            # colors
            {'colour': '#ff0000;invalid;AliceBlue'},
            TagFormat('colour', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:colour'),
            [
                TagFormat('#ff0000', 'color', '#ff0000'),
                TagFormat('invalid'),
                TagFormat('AliceBlue', 'color', 'AliceBlue'),
            ],
        ),
        (
            # emails
            {'email': 'support@openstreetmap.org;example@example.com'},
            TagFormat('email', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:email'),
            [
                TagFormat('support@openstreetmap.org', 'email', 'mailto:support@openstreetmap.org'),
                TagFormat('example@example.com', 'email', 'mailto:example@example.com'),
            ],
        ),
        (
            # phones
            {'phone': '+1-234-567-8901;+7925805204786492'},
            TagFormat('phone', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:phone'),
            [
                TagFormat('+1-234-567-8901', 'phone', 'tel:+12345678901'),
                TagFormat('+7925805204786492'),
            ],
        ),
        (
            # urls
            {'url': 'HTTPS://www.openstreetmap.org;ftp://www.openstreetmap.org'},
            TagFormat('url', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:url'),
            [
                TagFormat('HTTPS://www.openstreetmap.org', 'url', 'HTTPS://www.openstreetmap.org'),
                TagFormat('ftp://www.openstreetmap.org'),
            ],
        ),
        (
            # wikipedia with fragment
            {'wikipedia': 'Test#abc'},
            TagFormat('wikipedia', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:wikipedia'),
            [TagFormat('Test#abc', 'url-safe', 'https://en.wikipedia.org/wiki/Test#abc')],
        ),
        (
            # regional wikipedia
            {'pl:wikipedia': 'Test'},
            TagFormat('pl:wikipedia'),
            [TagFormat('Test', 'url-safe', 'https://pl.wikipedia.org/wiki/Test')],
        ),
        (
            # wikidata id
            {'wikidata': 'q123'},
            TagFormat('wikidata', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikidata'),
            [TagFormat('q123', 'url-safe', 'https://www.wikidata.org/entity/q123')],
        ),
        (
            # commons file prefix
            {'wikimedia_commons': 'file:Test'},
            TagFormat('wikimedia_commons', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons'),
            [TagFormat('file:Test', 'url-safe', 'https://commons.wikimedia.org/wiki/file:Test')],
        ),
        (
            # commons category prefix
            {'wikimedia_commons': 'Category:Test'},
            TagFormat('wikimedia_commons', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons'),
            [TagFormat('Category:Test', 'url-safe', 'https://commons.wikimedia.org/wiki/Category:Test')],
        ),
        (
            # full osm wiki key/tag support
            {'amenity': 'bench'},
            TagFormat('amenity', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:amenity'),
            [TagFormat('bench', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Tag:amenity=bench')],
        ),
    ],
)
def test_tags_format(tags: dict, key: TagFormat, vals: Sequence[TagFormat]):
    with translation_context('pl'):
        formatted = tags_format(tags)
        collection = next(iter(formatted.values()))
        assert key == collection.key
        assert tuple(vals) == tuple(collection.values)
