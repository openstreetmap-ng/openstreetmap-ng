from app.lib.text.local_chapters import LOCAL_CHAPTERS


def test_local_chapter_pl():
    assert ('OSM-PL-chapter', 'https://openstreetmap.org.pl/') in LOCAL_CHAPTERS
