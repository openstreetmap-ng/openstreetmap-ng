import pytest

from app.lib.changeset_note import parse_note_close_actions


def test_parse_note_close_actions_comment_precedence():
    actions = parse_note_close_actions({
        'closes:note': '10; 20;30',
        'comment': 'changeset comment',
        'closes:note:comment': 'global comment',
        'closes:note:20:comment': 'specific comment',
        'closes:note:30:comment': '',
    })

    assert actions == [
        (10, 'global comment'),
        (20, 'specific comment'),
        (30, ''),
    ]


@pytest.mark.parametrize(
    ('tags', 'expected'),
    [
        ({}, []),
        ({'closes:note': '1;1;2'}, [(1, ''), (2, '')]),
        ({'closes:note': 'invalid;0;-1;3'}, [(3, '')]),
        ({'closes:note': str(1 << 63)}, []),
        (
            {'closes:note': '4', 'comment': 'changeset comment'},
            [(4, 'changeset comment')],
        ),
    ],
)
def test_parse_note_close_actions(tags, expected):
    assert parse_note_close_actions(tags) == expected
