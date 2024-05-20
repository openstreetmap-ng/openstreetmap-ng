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
            TagFormat('comment', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:comment?uselang=pl'),
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
            TagFormat('colour', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:colour?uselang=pl'),
            [
                TagFormat('#ff0000', 'color', '#ff0000'),
                TagFormat('invalid'),
                TagFormat('AliceBlue', 'color', 'AliceBlue'),
            ],
        ),
        (
            # emails
            {'email': 'support@openstreetmap.org;example@example.com'},
            TagFormat('email', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:email?uselang=pl'),
            [
                TagFormat('support@openstreetmap.org', 'email', 'mailto:support@openstreetmap.org'),
                TagFormat('example@example.com', 'email', 'mailto:example@example.com'),
            ],
        ),
        (
            # phones
            {'phone': '+1-234-567-8901;+7925805204786492'},
            TagFormat('phone', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:phone?uselang=pl'),
            [
                TagFormat('+1-234-567-8901', 'phone', 'tel:+12345678901'),
                TagFormat('+7925805204786492'),
            ],
        ),
        (
            # urls
            {'url': 'HTTPS://www.openstreetmap.org;ftp://www.openstreetmap.org'},
            TagFormat('url', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:url?uselang=pl'),
            [
                TagFormat('HTTPS://www.openstreetmap.org', 'url', 'HTTPS://www.openstreetmap.org'),
                TagFormat('ftp://www.openstreetmap.org'),
            ],
        ),
        (
            # wikipedia with fragment
            {'wikipedia': 'Test#abc'},
            TagFormat('wikipedia', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:wikipedia?uselang=pl'),
            [TagFormat('Test#abc', 'url-safe', 'https://en.wikipedia.org/wiki/Test?uselang=pl#abc')],
        ),
        (
            # regional wikipedia
            {'pl:wikipedia': 'Test'},
            TagFormat('pl:wikipedia'),
            [TagFormat('Test', 'url-safe', 'https://pl.wikipedia.org/wiki/Test?uselang=pl')],
        ),
        (
            # wikidata id
            {'wikidata': 'q123'},
            TagFormat('wikidata', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikidata?uselang=pl'),
            [TagFormat('q123', 'url-safe', 'https://www.wikidata.org/entity/q123?uselang=pl')],
        ),
        (
            # commons file prefix
            {'wikimedia_commons': 'file:Test'},
            TagFormat(
                'wikimedia_commons', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons?uselang=pl'
            ),
            [TagFormat('file:Test', 'url-safe', 'https://commons.wikimedia.org/wiki/file:Test?uselang=pl')],
        ),
        (
            # commons category prefix
            {'wikimedia_commons': 'Category:Test'},
            TagFormat(
                'wikimedia_commons', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons?uselang=pl'
            ),
            [TagFormat('Category:Test', 'url-safe', 'https://commons.wikimedia.org/wiki/Category:Test?uselang=pl')],
        ),
        (
            # full osm wiki key/tag support
            {'amenity': 'bench'},
            TagFormat('amenity', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:amenity?uselang=pl'),
            [TagFormat('bench', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Tag:amenity=bench?uselang=pl')],
        ),
    ],
)
def test_tags_format(tags: dict, key: TagFormat, vals: Sequence[TagFormat]):
    with translation_context('pl'):
        formatted = tags_format(tags)
        collection = next(iter(formatted.values()))
        assert key == collection.key
        assert tuple(vals) == tuple(collection.values)
