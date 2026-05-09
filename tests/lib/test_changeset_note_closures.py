from app.lib.changeset_note_closures import changeset_note_closures


def test_changeset_note_closures_use_changeset_comment_by_default():
    assert changeset_note_closures({
        'comment': 'Close mapped notes',
        'closes:note': '12;34',
    }) == [(12, 'Close mapped notes'), (34, 'Close mapped notes')]


def test_changeset_note_closures_support_global_and_per_note_comments():
    assert changeset_note_closures({
        'comment': 'Ignored default',
        'closes:note': '12;34',
        'closes:note:comment': 'Global note close comment',
        'closes:note:34:comment': 'Specific note close comment',
    }) == [
        (12, 'Global note close comment'),
        (34, 'Specific note close comment'),
    ]


def test_changeset_note_closures_ignore_invalid_and_duplicate_ids():
    assert changeset_note_closures({
        'closes:note': '12;abc;0;-5;12;34;',
    }) == [(12, ''), (34, '')]
