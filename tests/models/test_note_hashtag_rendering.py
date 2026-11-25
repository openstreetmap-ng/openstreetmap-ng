from datetime import UTC, datetime
from unittest.mock import AsyncMock

from app.models.db import note_comment
from app.models.db.note_comment import note_comments_resolve_rich_text


async def test_rich_text_uses_snapshot_without_mutating_body_and_handles_duplicates(
    monkeypatch,
):
    first = {
        'id': 1,
        'user_id': None,
        'user_ip': None,
        'note_id': 7,
        'event': 'opened',
        'body': '',
        'tags': {'hashtags': '#old'},
        'body_rich_hash': None,
        'created_at': datetime.now(UTC),
    }
    duplicate = first.copy()
    second = {**first, 'id': 2, 'body': 'Checked', 'tags': {'hashtags': '#new'}}

    async def render(comments, table, key, style):
        assert (table, key, style) == ('note_comment', 'body', 'plain')
        assert [comment['body'] for comment in comments] == ['#old', 'Checked\n#new']
        for comment in comments:
            comment['body_rich'] = f'<p>{comment["body"]}</p>'
            comment['body_rich_hash'] = b'cached'

    renderer = AsyncMock(side_effect=render)
    monkeypatch.setattr(note_comment, 'resolve_rich_text', renderer)
    await note_comments_resolve_rich_text([first, duplicate, second])
    renderer.assert_awaited_once()
    assert first['body'] == duplicate['body'] == ''
    assert second['body'] == 'Checked'
    assert first['body_rich'] == duplicate['body_rich'] == '<p>#old</p>'
    assert second['body_rich'] == '<p>Checked\n#new</p>'
    assert first['body_rich_hash'] == duplicate['body_rich_hash'] == b'cached'
