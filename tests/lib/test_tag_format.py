from app.lib.tag_format import TagFormatted, tag_format
from app.lib.translation import translation_context
from app.models.tag_format import TagFormat


def test_tag_format_colour():
    assert tag_format('colour', '') == ()
    assert tag_format('colour', '#ff0000;invalid;AliceBlue') == (
        TagFormatted(TagFormat.color, '#ff0000', '#ff0000'),
        TagFormatted(TagFormat.default, 'invalid', 'invalid'),
        TagFormatted(TagFormat.color, 'AliceBlue', 'AliceBlue'),
    )
    assert tag_format('colour', '#ff00001; #ff0000') == (
        TagFormatted(TagFormat.default, '#ff00001', '#ff00001'),
        TagFormatted(TagFormat.default, ' #ff0000', ' #ff0000'),
    )


def test_tag_format_email():
    assert tag_format('email', 'support@openstreetmap.org;example@example.com') == (
        TagFormatted(TagFormat.email, 'support@openstreetmap.org', 'mailto:support@openstreetmap.org'),
        TagFormatted(TagFormat.email, 'example@example.com', 'mailto:example@example.com'),
    )
    assert tag_format('email', 'invalid email address') == (
        TagFormatted(TagFormat.default, 'invalid email address', 'invalid email address'),
    )


def test_tag_format_phone():
    assert tag_format('phone', '+1-234-567-8901;+7925805204786492') == (
        TagFormatted(TagFormat.phone, '+1-234-567-8901', 'tel:+12345678901'),
        TagFormatted(TagFormat.default, '+7925805204786492', '+7925805204786492'),
    )
    assert tag_format('fax', '+1-234-567-8901') == (
        TagFormatted(TagFormat.phone, '+1-234-567-8901', 'tel:+12345678901'),
    )


def test_tag_format_url():
    assert tag_format('url', 'https://www.openstreetmap.org;ftp://www.openstreetmap.org') == (
        TagFormatted(TagFormat.url, 'https://www.openstreetmap.org', 'https://www.openstreetmap.org'),
        TagFormatted(TagFormat.default, 'ftp://www.openstreetmap.org', 'ftp://www.openstreetmap.org'),
    )
    assert tag_format('website', 'HTTPS://WWW.OSM.ORG') == (
        TagFormatted(TagFormat.url, 'HTTPS://WWW.OSM.ORG', 'HTTPS://WWW.OSM.ORG'),
    )


def test_tag_format_wikipedia():
    with translation_context('pl'):
        assert tag_format('wikipedia', 'Test') == (
            TagFormatted(TagFormat.url, 'Test', 'https://en.wikipedia.org/wiki/Test?uselang=pl'),
        )
        assert tag_format('wikipedia', 'Test#abc') == (
            TagFormatted(TagFormat.url, 'Test#abc', 'https://en.wikipedia.org/wiki/Test?uselang=pl#abc'),
        )
        assert tag_format('pl:wikipedia', 'Test') == (
            TagFormatted(TagFormat.url, 'Test', 'https://pl.wikipedia.org/wiki/Test?uselang=pl'),
        )


def test_tag_format_wikidata():
    with translation_context('pl'):
        assert tag_format('wikidata', 'Q123') == (
            TagFormatted(TagFormat.url, 'Q123', 'https://www.wikidata.org/entity/Q123?uselang=pl'),
        )
        assert tag_format('wikidata', 'q123') == (
            TagFormatted(TagFormat.url, 'q123', 'https://www.wikidata.org/entity/q123?uselang=pl'),
        )


def test_tag_format_wikimedia_commons():
    with translation_context('pl'):
        assert tag_format('wikimedia_commons', 'File:Test') == (
            TagFormatted(TagFormat.url, 'File:Test', 'https://commons.wikimedia.org/wiki/File:Test?uselang=pl'),
        )
        assert tag_format('wikimedia_commons', 'file:Test') == (
            TagFormatted(TagFormat.url, 'file:Test', 'https://commons.wikimedia.org/wiki/file:Test?uselang=pl'),
        )
        assert tag_format('wikimedia_commons', 'Category:Test') == (
            TagFormatted(TagFormat.url, 'Category:Test', 'https://commons.wikimedia.org/wiki/Category:Test?uselang=pl'),
        )
