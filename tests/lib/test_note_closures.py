import pytest

from app.lib.note_closures import note_closures


@pytest.mark.parametrize(
    ('tags', 'expected'),
    [
        ({}, {}),
        ({'closes:note': '1;2', 'comment': 'fixed'}, {1: 'fixed', 2: 'fixed'}),
        (
            {
                'closes:note': '1;2',
                'comment': 'default',
                'closes:note:comment': 'global',
                'closes:note:2:comment': 'individual',
            },
            {1: 'global', 2: 'individual'},
        ),
        (
            {
                'closes:note': '1;2',
                'comment': 'default',
                'closes:note:comment': '',
                'closes:note:2:comment': '',
            },
            {1: '', 2: ''},
        ),
        ({'closes:note': ' 1;01;1;2 '}, {1: '', 2: ''}),
        ({'closes:note': '-1;0;foo;1.2;9223372036854775808;\uff19;3'}, {3: ''}),
        ({'closes:note': '9223372036854775807'}, {9223372036854775807: ''}),
    ],
)
def test_note_closures(tags, expected):
    assert note_closures(tags) == expected
