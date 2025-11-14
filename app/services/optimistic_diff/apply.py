from datetime import datetime
from io import BytesIO

import cython
from psycopg import AsyncConnection
from psycopg.sql import SQL

from app.db import db
from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.lib.compressible_geometry import compressible_geometry
from app.lib.date_utils import utcnow
from app.models.db.changeset import Changeset
from app.models.db.element import Element, ElementInit
from app.models.element import ElementId, ElementType, TypedElementId
from app.models.types import SequenceId
from app.queries.element_query import ElementQuery
from app.services.audit_service import audit
from app.services.optimistic_diff.prepare import (
    ElementStateEntry,
    OptimisticDiffPrepare,
)
from speedup.element_type import split_typed_element_id, typed_element_id


class OptimisticDiffApply:
    @staticmethod
    async def apply(
        prepare: OptimisticDiffPrepare,
    ) -> dict[TypedElementId, tuple[TypedElementId, list[int]]]:
        """
        Apply the optimistic diff update.
        Returns a dict, mapping original element refs to the new versions.
        """
        if not prepare.apply_elements:
            return {}

        for element in prepare.apply_elements:
            if (point := element['point']) is not None:
                element['point'] = compressible_geometry(point)

        async with db(True) as conn:
            await audit(
                'edit_map',
                conn,
                extra={
                    'changeset': prepare.changeset['id'],
                    'size': len(prepare.apply_elements),
                },
            )

            # Lock the tables to avoid concurrent updates.
            # Then perform all the updates at once.
            await conn.execute(
                'LOCK TABLE changeset, changeset_bounds, element IN EXCLUSIVE MODE'
            )

            # Check if the elements have no new references
            if prepare.reference_check_element_refs:
                await _check_elements_unreferenced(
                    conn,
                    prepare.reference_check_element_refs,
                    prepare.at_sequence_id,
                )

            # Process elements and changeset updates
            now = utcnow()
            await _update_changeset(conn, now, prepare.changeset)
            assigned_id_map: dict[TypedElementId, TypedElementId]
            assigned_id_map = await _update_elements(
                conn, now, prepare.element_state, prepare.apply_elements
            )

        # Build result mapping
        result: dict[TypedElementId, tuple[TypedElementId, list[int]]] = {}

        for element in prepare.apply_elements:
            typed_id = element['typed_id']
            version = element['version']

            if typed_id not in result:
                result[typed_id] = (
                    # Lookup negative ids in the assigned map.
                    assigned_id_map[typed_id] if typed_id & 1 << 59 else typed_id,
                    [version],
                )
            else:
                result[typed_id][1].append(version)

        return result


async def _check_elements_unreferenced(
    conn: AsyncConnection,
    typed_ids: set[TypedElementId],
    after_sequence_id: SequenceId,
) -> None:
    """
    Check if the elements are currently unreferenced.
    Raises OptimisticDiffError if they are.
    """
    if not await ElementQuery.check_is_unreferenced(
        conn, list(typed_ids), after_sequence_id
    ):
        raise OptimisticDiffError(f'Element is referenced after {after_sequence_id}')


async def _update_changeset(
    conn: AsyncConnection, now: datetime, changeset: Changeset
) -> None:
    """
    Update the changeset table.
    Raises OptimisticDiffError if the changeset was modified in the meantime.
    """
    changeset_id = changeset['id']
    closed_at = now if 'size_limit_reached' in changeset else None
    updated_at = now

    result = await conn.execute(
        """
        UPDATE changeset
        SET
            size = %s,
            num_create = %s,
            num_modify = %s,
            num_delete = %s,
            union_bounds = ST_QuantizeCoordinates(%s, 7),
            closed_at = %s,
            updated_at = %s
        WHERE id = %s AND updated_at = %s
        """,
        (
            changeset['size'],
            changeset['num_create'],
            changeset['num_modify'],
            changeset['num_delete'],
            changeset['union_bounds'],
            closed_at,
            updated_at,
            changeset_id,
            changeset['updated_at'],
        ),
    )

    if not result.rowcount:
        raise OptimisticDiffError(f'Changeset {changeset_id} is outdated')

    # Update the changeset bounds
    # It's not possible for bounds to switch from MultiPolygon to None.
    bounds = changeset.get('bounds')
    if bounds is None:
        return

    await conn.execute(
        """
        DELETE FROM changeset_bounds
        WHERE changeset_id = %s
        """,
        (changeset_id,),
    )
    await conn.execute(
        """
        INSERT INTO changeset_bounds (changeset_id, bounds)
        SELECT %s, (ST_Dump(ST_QuantizeCoordinates(%s, 7))).geom
        """,
        (changeset_id, bounds),
    )


async def _update_elements(
    conn: AsyncConnection,
    now: datetime,
    element_state: dict[TypedElementId, ElementStateEntry],
    elements_init: list[ElementInit],
) -> dict[TypedElementId, TypedElementId]:
    """Update the element table by creating new revisions."""
    current_sequence_id = await ElementQuery.get_current_sequence_id(conn)
    current_id_map: dict[ElementType, ElementId]
    current_id_map = await ElementQuery.get_current_ids(conn)

    elements: list[Element] = []
    prev_map: dict[TypedElementId, Element] = {}
    assigned_id_map: dict[TypedElementId, TypedElementId] = {}

    # This compiled check is slightly misleading.
    # Cython will always use the first declaration.
    if cython.compiled:
        element_init: dict  # type: ignore
    else:
        element_init: ElementInit

    # Process elements and prepare data for insert
    for sequence_id, element_init in enumerate(elements_init, current_sequence_id + 1):
        element: Element = {
            **element_init,
            'sequence_id': sequence_id,  # type: ignore
            'latest': True,
            'created_at': now,
        }
        elements.append(element)
        typed_id = element['typed_id']

        # Assign ids for new elements
        if typed_id & 1 << 59:
            original_typed_id = typed_id
            if original_typed_id in assigned_id_map:
                # Reuse already assigned id
                typed_id = assigned_id_map[original_typed_id]
            else:
                # Assign a new id
                type = split_typed_element_id(typed_id)[0]
                new_id: ElementId = current_id_map[type] + 1  # type: ignore
                current_id_map[type] = new_id
                typed_id = typed_element_id(type, new_id)
                assigned_id_map[original_typed_id] = typed_id
            element['typed_id'] = typed_id

        # Update the latest flag for changed elements (local)
        prev = prev_map.get(typed_id)
        if prev is not None:
            prev['latest'] = False
        prev_map[typed_id] = element

    # Update members with assigned ids
    for element in elements:
        # TODO: tainted members check in the prepare phase
        if members := element['members']:
            element['members'] = [
                assigned_id_map[member]  #
                if member & 1 << 59
                else member
                for member in members
            ]

    await _update_latest_elements(conn, element_state)
    await _copy_elements(conn, elements)
    return assigned_id_map


async def _update_latest_elements(
    conn: AsyncConnection, element_state: dict[TypedElementId, ElementStateEntry]
) -> None:
    """Update the latest flag for changed elements (remote)."""
    params = [
        v
        for typed_id, entry in element_state.items()
        if entry.remote is not None
        for v in (typed_id, entry.remote['version'])
    ]
    if not params:
        return

    num_rows = len(params) // 2
    result = await conn.execute(
        SQL("""
            UPDATE element e SET latest = FALSE
            FROM (VALUES {}) AS v(typed_id, version)
            WHERE e.typed_id = v.typed_id
            AND e.version = v.version
            AND e.latest
        """).format(SQL(',').join([SQL('(%s, %s)')] * num_rows)),
        params,
    )
    if result.rowcount != num_rows:
        raise OptimisticDiffError('Element is outdated')


async def _copy_elements(conn: AsyncConnection, elements: list[Element]) -> None:
    async with conn.cursor().copy("""
        COPY element (
            sequence_id, created_at,
            changeset_id, typed_id, version, latest,
            visible, tags, point, members, members_roles
        ) FROM STDIN
    """) as copy:
        with BytesIO() as buffer:
            write_row = copy.formatter.write_row

            # This compiled check is slightly misleading.
            # Cython will always use the first declaration.
            if cython.compiled:
                element: dict  # type: ignore
            else:
                element: Element

            for element in elements:
                data = write_row((
                    element['sequence_id'],
                    element['created_at'],
                    element['changeset_id'],
                    element['typed_id'],
                    element['version'],
                    element['latest'],
                    element['visible'],
                    element['tags'],
                    element['point'],
                    element['members'],
                    element['members_roles'],
                ))
                if data:
                    buffer.write(data)

            data = buffer.getvalue()
            await copy.write(data)
