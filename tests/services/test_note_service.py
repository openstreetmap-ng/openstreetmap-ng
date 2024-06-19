import pytest
from shapely import Point
from sqlalchemy import select

from app.db import db_commit
from app.models.db.note import Note
from app.services.note_service import NoteService

pytestmark = pytest.mark.anyio


async def test_delete_note_without_comments():
    async with db_commit() as session:
        note = Note(point=Point(0, 0), comments=[])
        session.add(note)

    async with db_commit() as session:
        stmt = select(Note).where(Note.id == note.id)
        note_selected = await session.scalar(stmt)

    assert note.id == note_selected.id
    assert len(note.comments) == 0

    await NoteService.delete_notes_without_comments()

    async with db_commit() as session:
        stmt = select(Note).where(Note.id == note_selected.id)
        note = await session.scalar(stmt)

    assert note is None
