import pytest
from shapely import Point
from sqlalchemy import select

from app.db import db, db_commit
from app.models.db.note import Note
from app.services.note_service import NoteService


@pytest.mark.skip('Slow test')
async def test_delete_note_without_comments():
    async with db_commit() as session:
        note = Note(point=Point(0, 0))
        session.add(note)

    async with db() as session:
        stmt = select(Note).where(Note.id == note.id)
        note_selected = (await session.execute(stmt)).scalar_one()

    assert note.id == note_selected.id

    await NoteService.delete_notes_without_comments()

    async with db() as session:
        stmt = select(Note).where(Note.id == note.id)
        note_selected = await session.scalar(stmt)

    assert note_selected is None
