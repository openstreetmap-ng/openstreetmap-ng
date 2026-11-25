import pytest

from app.lib.text.note_hashtags import append_note_hashtags, extract_note_hashtags


@pytest.mark.parametrize(
    'text',
    [
        '',
        'Ordinary comment',
        'https://example.org/path#survey',
        'https://example.org/?q=#survey',
        'https://example.org/#survey',
        'name#mail@example.org',
        '# Heading',
        '## heading',
        '#___ #---',
    ],
)
def test_non_hashtags_are_unchanged(text):
    assert extract_note_hashtags(text) == (text, None)


def test_distinct_hashtags_keep_order_and_case():
    body, tags = extract_note_hashtags(
        'Check this road.\n#survey #osm-ng #survey #Survey'
    )
    assert body == 'Check this road.'
    assert tags == {'hashtags': '#survey;#osm-ng;#Survey'}
    assert (
        append_note_hashtags(body, tags) == 'Check this road.\n#survey #osm-ng #Survey'
    )


def test_unicode_letters_and_combining_marks_are_not_split():
    assert extract_note_hashtags('#cafe\u0301 #مَسح #東京 #42') == (
        '',
        {'hashtags': '#cafe\u0301;#مَسح;#東京;#42'},
    )


def test_punctuation_and_url_are_preserved():
    assert extract_note_hashtags(
        'Check #survey, then https://example.org/#building'
    ) == (
        'Check , then https://example.org/#building',
        {'hashtags': '#survey'},
    )


def test_hashtag_only_comment_remains_visible_on_output():
    body, tags = extract_note_hashtags('#survey #needs_imagery')
    assert body == ''
    assert append_note_hashtags(body, tags) == '#survey #needs_imagery'


def test_unrelated_tags_do_not_leak_into_legacy_text():
    assert append_note_hashtags('Comment', {'source': 'private review'}) == 'Comment'


@pytest.mark.parametrize('tags', [None, {}, {'hashtags': ''}])
def test_comment_without_tag_change_keeps_its_text(tags):
    assert append_note_hashtags('Comment', tags) == 'Comment'


def test_tag_value_limit_does_not_truncate_or_remove_text():
    accepted = '#' + 'a' * 254
    assert extract_note_hashtags(accepted) == ('', {'hashtags': accepted})
    oversized = 'Before ' + accepted + ' #b after'
    assert extract_note_hashtags(oversized) == (oversized, None)


def test_duplicate_tokens_do_not_consume_value_budget():
    token = '#' + 'a' * 254
    assert extract_note_hashtags(f'{token} {token}') == ('', {'hashtags': token})


def test_extract_append_reaches_stable_representation():
    body, tags = extract_note_hashtags('A road\n#survey #osm-ng #survey')
    assert extract_note_hashtags(append_note_hashtags(body, tags)) == (body, tags)
