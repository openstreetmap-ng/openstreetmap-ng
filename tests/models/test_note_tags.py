from unittest.mock import AsyncMock

import pytest

from app.db import db_fetchone, db_update
from app.lib.auth.context import auth_context
from app.lib.text.locale import DEFAULT_LOCALE
from app.lib.text.translation import translation_context
from app.models.db.note import Note
from app.models.db.note_comment import note_comments_resolve_rich_text
from app.models.types import DisplayName
from app.queries.nominatim_query import NominatimQuery
from app.queries.note_query import NoteCommentQuery
from app.queries.user_query import UserQuery
from app.services.migration_service import MigrationService
from app.services.note_service import NoteService


@pytest.fixture(autouse=True)
def _local_geocoding(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(NominatimQuery, 'reverse', AsyncMock(return_value=None))


async def test_note_tag_snapshots_and_explicit_clear():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    with (
        translation_context(DEFAULT_LOCALE),
        auth_context(user, frozenset(('web_user',))),
    ):
        note_id = await NoteService.create(
            0, 0, 'Original', tags={'hashtags': '#survey'}
        )
        await NoteService.comment(note_id, 'Keep tags', 'commented')
        note = await db_fetchone(Note, t'SELECT * FROM note WHERE id = {note_id}')
        assert note is not None and note['tags'] == {'hashtags': '#survey'}
        await NoteService.comment(note_id, 'Clear tags', 'commented', tags={})
        note = await db_fetchone(Note, t'SELECT * FROM note WHERE id = {note_id}')
        assert note is not None and note['tags'] == {}
        comments = await NoteCommentQuery.resolve_comments(
            [note], per_note_sort='asc', per_note_limit=None
        )
        assert [c['tags'] for c in comments] == [{'hashtags': '#survey'}, None, {}]
        assert comments[0]['body'] == 'Original'


async def test_note_hashtag_backfill_is_resumable_and_preserves_newer_edits():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    with (
        translation_context(DEFAULT_LOCALE),
        auth_context(user, frozenset(('web_user',))),
    ):
        note_id = await NoteService.create(0, 0, 'Legacy #survey')
        header = await NoteCommentQuery.find_header(note_id)
        assert header is not None
        # Simulate a pre-migration opening comment, then a modern explicit edit.
        await db_update('note_comment', {'tags': None}, where={'id': header['id']})
        await NoteService.comment(
            note_id, 'Resolved', 'closed', tags={'hashtags': '#solved'}
        )
        await MigrationService.migrate_note_hashtags(batch_size=1)
        await MigrationService.migrate_note_hashtags(batch_size=1)
        # A reader that fetched the old body before the backfill must not
        # restore a stale rich-text hash after the backfill commits.
        await note_comments_resolve_rich_text([header])
        current_header = await NoteCommentQuery.find_header(note_id)
        assert current_header is not None
        await note_comments_resolve_rich_text([current_header])
        rendered = current_header.get('body_rich')
        assert rendered is not None and '#survey' not in rendered
        note = await db_fetchone(Note, t'SELECT * FROM note WHERE id = {note_id}')
        assert note is not None and note['tags'] == {'hashtags': '#solved'}
        comments = await NoteCommentQuery.resolve_comments(
            [note], per_note_sort='asc', per_note_limit=None
        )
        assert [c['body'] for c in comments] == ['Legacy', 'Resolved']
        assert [c['tags'] for c in comments] == [
            {'hashtags': '#survey'},
            {'hashtags': '#solved'},
        ]
