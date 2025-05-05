import pytest
from shapely import Point

from app.db import db
from app.lib.auth_context import auth_context
from app.models.db.element import ElementInit
from app.models.db.note import NoteInit
from app.models.element import ElementId, typed_element_id
from app.models.types import ChangesetId
from app.queries.element_query import ElementQuery
from app.queries.note_query import NoteQuery
from app.services.migration_service import (
    MigrationService,
    _get_element_typed_id_batches,  # noqa: PLC2701
)
from app.services.optimistic_diff import OptimisticDiff
from tests.utils.assert_model import assert_model


@pytest.mark.extended
async def test_deduplicate_elements(changeset_id: ChangesetId):
    elements: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-1)),
            'version': i,
            'visible': True,
            'tags': None,
            'point': Point(0, 0),
            'members': None,
            'members_roles': None,
        }
        for i in range(1, 3)
    ]

    # Create the elements
    assigned_ref_map = await OptimisticDiff.run(elements)
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Patch the 2nd element to create a duplicate
    async with db(True) as conn:
        result = await conn.execute(
            """
            UPDATE element SET version = 1
            WHERE typed_id = %s AND version = 2
            """,
            (typed_id,),
        )
        assert result.rowcount == 1

    # Run the migration service method
    await MigrationService.deduplicate_elements()

    # Verify the duplicate was removed
    async with (
        db() as conn,
        await conn.execute(
            """
            SELECT COUNT(*) FROM element
            WHERE typed_id = %s
            """,
            (typed_id,),
        ) as r,
    ):
        count = (await r.fetchone())[0]  # type: ignore
        assert count == 1


@pytest.mark.extended
async def test_mark_latest_elements(changeset_id: ChangesetId):
    elements: list[ElementInit] = [
        {
            'changeset_id': changeset_id,
            'typed_id': typed_element_id('node', ElementId(-1)),
            'version': i,
            'visible': True,
            'tags': None,
            'point': Point(0, 0),
            'members': None,
            'members_roles': None,
        }
        for i in range(1, 4)
    ]

    # Create the elements
    assigned_ref_map = await OptimisticDiff.run(elements)
    typed_id = assigned_ref_map[typed_element_id('node', ElementId(-1))][0]

    # Set the latest flag to FALSE to create an incorrect state
    async with db(True) as conn:
        result = await conn.execute(
            """
            UPDATE element SET latest = FALSE
            WHERE typed_id = %s
            AND latest
            """,
            (typed_id,),
        )
        assert result.rowcount == 1

    # Run the migration service method
    await MigrationService.mark_latest_elements()

    # Verify the correct element now has latest=TRUE
    assert_model(
        (await ElementQuery.get_by_refs([typed_id], limit=1))[0],
        {
            'version': 3,
            'latest': True,
        },
    )


@pytest.mark.extended
async def test_delete_note_without_comments():
    with auth_context(None, ()):
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
        assert await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)

        # Run the migration service method
        await MigrationService.delete_notes_without_comments()

        # Verify the note was deleted
        assert not await NoteQuery.find_many_by_query(note_ids=[note_id], limit=1)


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
