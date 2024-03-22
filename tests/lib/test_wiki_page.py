from app.lib.translation import translation_context
from app.lib.wiki_page import wiki_page


def test_wiki_page():
    with translation_context('pl'):
        assert wiki_page('colour', 'value') == 'https://wiki.openstreetmap.org/wiki/Pl:Key:colour?uselang=pl'
        assert wiki_page('amenity', 'bench') == 'https://wiki.openstreetmap.org/wiki/Pl:Tag:amenity=bench?uselang=pl'
        assert wiki_page('non_existing_key', '') is None
