from app.lib.local_chapters import local_chapters


def test_local_chapter_pl():
    assert ('OSM-PL-chapter', 'https://openstreetmap.org.pl/') in local_chapters()
