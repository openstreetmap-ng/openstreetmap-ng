from app.lib.changeset_note_closures import parse_changeset_note_closures
from app.models.types import NoteId


def test_parse_changeset_note_closures():
    assert parse_changeset_note_closures({
        'comment': 'default comment',
        'closes:note': ' 12 ;invalid;34;12;0;',
        'closes:note:34:comment': 'custom comment',
    }) == {
        NoteId(12): 'default comment',
        NoteId(34): 'custom comment',
    }


def test_parse_changeset_note_closures_shared_override():
    assert parse_changeset_note_closures({
        'comment': 'changeset comment',
        'closes:note': '5;6',
        'closes:note:comment': 'shared note comment',
    }) == {
        NoteId(5): 'shared note comment',
        NoteId(6): 'shared note comment',
    }


def test_parse_changeset_note_closures_without_comment():
    assert parse_changeset_note_closures({'closes:note': '7'}) == {NoteId(7): ''}
    assert parse_changeset_note_closures({'comment': 'unused'}) == {}
