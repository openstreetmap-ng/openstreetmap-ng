from app.services.note_service import with_note_app_hashtag


def test_with_note_app_hashtag_appends_hashtag():
    assert with_note_app_hashtag('Missing path here') == 'Missing path here\n\n#osm-ng'


def test_with_note_app_hashtag_preserves_existing_hashtag_case_insensitive():
    assert with_note_app_hashtag('Missing path here #OSM-NG') == 'Missing path here #OSM-NG'


def test_with_note_app_hashtag_trims_trailing_whitespace_before_append():
    assert with_note_app_hashtag('Missing path here  \n') == 'Missing path here\n\n#osm-ng'
