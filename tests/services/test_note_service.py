import pytest
from shapely import Point

from app.db import db
from app.models.db.note import NoteInit
from app.models.types import NoteId
from app.queries.note_query import NoteQuery
from app.services.note_service import NoteService


@pytest.mark.extended
async def test_delete_note_without_comments():
    # Create a note without comments
    note_id = await _create_note()

    # Verify the note exists before deletion
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    assert notes, 'Test note must exist before deletion'

    # Run the service method being tested
    await NoteService.delete_notes_without_comments()

    # Verify the note was deleted
    notes = await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)
    assert not notes, 'Note without comments must be deleted'


async def _create_note() -> NoteId:
    note_init: NoteInit = {
        'point': Point(0, 0),
    }

    async with (
        db(True) as conn,
        await conn.execute(
            """
            INSERT INTO note (point)
            VALUES (%(point)s)
            RETURNING id
            """,
            note_init,
        ) as r,
    ):
        return (await r.fetchone())[0]  # type: ignore
