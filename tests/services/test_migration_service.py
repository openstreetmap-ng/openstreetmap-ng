import pytest
from shapely import Point

from app.db import db
from app.lib.auth_context import auth_context
from app.models.db.note import NoteInit
from app.queries.note_query import NoteQuery
from app.services.migration_service import (
    MigrationService,
    _get_element_typed_id_batches,
)


@pytest.mark.extended
async def test_delete_note_without_comments():
    with auth_context(None):
        # Create a note without comments
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
            note_id = (await r.fetchone())[0]  # type: ignore

        # Verify the note exists before deletion
        assert await NoteQuery.find(note_ids=[note_id], limit=1)

        # Run the migration service method
        await MigrationService.delete_notes_without_comments()

        # Verify the note was deleted
        assert not await NoteQuery.find(note_ids=[note_id], limit=1)


@pytest.mark.parametrize(
    ('ranges', 'batch_size', 'expected'),
    [
        (
            [
                (0, 5),
                (11, 13),
                (15, 20),
            ],
            10,
            [(0, 15), (16, 20)],
        ),
        (
            [
                (0, 0),
                (5, 6),
            ],
            1,
            [(0, 0), (5, 5), (6, 6)],
        ),
    ],
)
def test_get_element_typed_id_batches(ranges, batch_size, expected):
    assert _get_element_typed_id_batches(ranges, batch_size) == expected
