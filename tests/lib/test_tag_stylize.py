from collections.abc import Sequence

from app.lib.tag_stylize import tag_stylize
from app.lib.translation import translation_context
from app.models.tag_style import TagStyle, TagStyleCollection


def test_tag_stylize():
    tests: Sequence[tuple[TagStyleCollection, TagStyle, Sequence[TagStyle]]] = [
        (
            # comment with potentially malicious content
            TagStyleCollection('comment', 'https://example.com <script>'),
            TagStyle('comment', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:comment?uselang=pl'),
            [
                TagStyle(
                    'https://example.com <script>',
                    'html',
                    '<a href="https://example.com" rel="nofollow">https://example.com</a> &lt;script&gt;',
                )
            ],
        ),
        (
            # colors
            TagStyleCollection('colour', '#ff0000;invalid;AliceBlue'),
            TagStyle('colour', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:colour?uselang=pl'),
            [
                TagStyle('#ff0000', 'color', '#ff0000'),
                TagStyle('invalid'),
                TagStyle('AliceBlue', 'color', 'AliceBlue'),
            ],
        ),
        (
            # emails
            TagStyleCollection('email', 'support@openstreetmap.org;example@example.com'),
            TagStyle('email', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:email?uselang=pl'),
            [
                TagStyle('support@openstreetmap.org', 'email', 'mailto:support@openstreetmap.org'),
                TagStyle('example@example.com', 'email', 'mailto:example@example.com'),
            ],
        ),
        (
            # phones
            TagStyleCollection('phone', '+1-234-567-8901;+7925805204786492'),
            TagStyle('phone', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:phone?uselang=pl'),
            [
                TagStyle('+1-234-567-8901', 'phone', 'tel:+12345678901'),
                TagStyle('+7925805204786492'),
            ],
        ),
        (
            # urls
            TagStyleCollection('url', 'HTTPS://www.openstreetmap.org;ftp://www.openstreetmap.org'),
            TagStyle('url', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:url?uselang=pl'),
            [
                TagStyle('HTTPS://www.openstreetmap.org', 'url', 'HTTPS://www.openstreetmap.org'),
                TagStyle('ftp://www.openstreetmap.org'),
            ],
        ),
        (
            # wikipedia with fragment
            TagStyleCollection('wikipedia', 'Test#abc'),
            TagStyle('wikipedia', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:wikipedia?uselang=pl'),
            [TagStyle('Test#abc', 'url-safe', 'https://en.wikipedia.org/wiki/Test?uselang=pl#abc')],
        ),
        (
            # regional wikipedia
            TagStyleCollection('pl:wikipedia', 'Test'),
            TagStyle('pl:wikipedia'),
            [TagStyle('Test', 'url-safe', 'https://pl.wikipedia.org/wiki/Test?uselang=pl')],
        ),
        (
            # wikidata id
            TagStyleCollection('wikidata', 'q123'),
            TagStyle('wikidata', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikidata?uselang=pl'),
            [TagStyle('q123', 'url-safe', 'https://www.wikidata.org/entity/q123?uselang=pl')],
        ),
        (
            # commons file prefix
            TagStyleCollection('wikimedia_commons', 'file:Test'),
            TagStyle(
                'wikimedia_commons', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons?uselang=pl'
            ),
            [TagStyle('file:Test', 'url-safe', 'https://commons.wikimedia.org/wiki/file:Test?uselang=pl')],
        ),
        (
            # commons category prefix
            TagStyleCollection('wikimedia_commons', 'Category:Test'),
            TagStyle(
                'wikimedia_commons', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons?uselang=pl'
            ),
            [TagStyle('Category:Test', 'url-safe', 'https://commons.wikimedia.org/wiki/Category:Test?uselang=pl')],
        ),
        (
            # full osm wiki key/tag support
            TagStyleCollection('amenity', 'bench'),
            TagStyle('amenity', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Key:amenity?uselang=pl'),
            [TagStyle('bench', 'url-safe', 'https://wiki.openstreetmap.org/wiki/Pl:Tag:amenity=bench?uselang=pl')],
        ),
    ]

    with translation_context('pl'):
        for tag, key, vals in tests:
            tags = [tag]
            tag_stylize(tags)
            assert key == tag.key
            assert tuple(vals) == tuple(tag.values)
