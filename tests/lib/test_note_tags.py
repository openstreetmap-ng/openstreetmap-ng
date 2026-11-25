import pytest

from app.lib.text.note_tags import (
    append_note_hashtags,
    extract_note_hashtags,
    valid_note_hashtags,
)


@pytest.mark.parametrize(
    'text',
    [
        '',
        'plain text',
        'https://example.org/map#survey',
        'name#tag',
        '## Heading',
        '# Heading',
        '#map/path',
        '#one#two',
        '<script>#tag</script>',
    ],
)
def test_non_hashtag_text_is_unchanged(text):
    assert extract_note_hashtags(text) == (text, None)


def test_extract_preserves_order_spelling_and_unicode():
    body, tags = extract_note_hashtags('Needs survey\n#서울 #cafe\u0301 #osm-ng #서울')
    assert body == 'Needs survey'
    assert tags == {'hashtags': '#서울;#cafe\u0301;#osm-ng'}
    assert valid_note_hashtags(tags['hashtags'])


def test_extract_does_not_remove_url_fragments():
    body, tags = extract_note_hashtags('https://example.org/#survey #survey')
    assert body == 'https://example.org/#survey'
    assert tags == {'hashtags': '#survey'}


def test_unicode_whitespace_and_punctuation_preserve_surrounding_text():
    assert extract_note_hashtags('Check\u2003#survey, then verify.') == (
        'Check\u2003, then verify.',
        {'hashtags': '#survey'},
    )


@pytest.mark.parametrize(
    'tags, expected',
    [
        (None, 'text'),
        ({}, 'text'),
        ({'source': 'survey'}, 'text'),
        ({'hashtags': '#survey;#osm-ng'}, 'text\n#survey #osm-ng'),
    ],
)
def test_legacy_append(tags, expected):
    assert append_note_hashtags('text', tags) == expected


def test_hashtag_only_comment_roundtrip():
    body, tags = extract_note_hashtags('#survey #osm-ng')
    assert body == ''
    assert append_note_hashtags(body, tags) == '#survey #osm-ng'


@pytest.mark.parametrize(
    'value, valid',
    [
        ('', True),
        ('#survey;#서울', True),
        ('#cafe\u0301', True),
        ('#osm-ng;#building_42', True),
        ('survey', False),
        ('#', False),
        ('#one;;#two', False),
        ('#one two', False),
        ('#one/#two', False),
        ('#one;<script>', False),
    ],
)
def test_validate_hashtags(value, valid):
    assert valid_note_hashtags(value) is valid
