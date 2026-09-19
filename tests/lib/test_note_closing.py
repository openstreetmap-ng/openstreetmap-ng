import pytest

from app.lib.note_closing import parse_note_closures


@pytest.mark.parametrize(
    ('tags', 'expected'),
    [
        ({}, []),
        ({'closed:note': '1'}, []),
        ({'closes:note': '2;1;2;001'}, [(1, ''), (2, '')]),
        (
            {'closes:note': ' 1 ; ;2 ', 'comment': 'Mapped'},
            [(1, 'Mapped'), (2, 'Mapped')],
        ),
        (
            {'closes:note': '1', 'comment': 'Mapped', 'closes:note:comment': 'Fixed'},
            [(1, 'Fixed')],
        ),
        (
            {
                'closes:note': '1;2',
                'closes:note:comment': 'Fixed',
                'closes:note:2:comment': 'Verified',
            },
            [(1, 'Fixed'), (2, 'Verified')],
        ),
        (
            {'closes:note': '1', 'comment': 'Mapped', 'closes:note:comment': ''},
            [(1, '')],
        ),
        (
            {
                'closes:note': '1',
                'closes:note:comment': 'Fixed',
                'closes:note:1:comment': '',
            },
            [(1, '')],
        ),
        ({'closes:note': '0;-1;+1;1.5;1e2;abc;\u0661;²'}, []),
        (
            {'closes:note': '9223372036854775807;9223372036854775808'},
            [(9223372036854775807, '')],
        ),
        ({'closes:note': '9' * 5000}, []),
        ({'closes:note': '0001', 'closes:note:1:comment': 'Done'}, [(1, 'Done')]),
    ],
)
def test_parse_note_closures(tags, expected):
    assert parse_note_closures(tags) == expected
