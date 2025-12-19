from datetime import datetime
from io import BytesIO

import cython
from psycopg import AsyncConnection

from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.lib.compressible_geometry import compressible_geometry
from app.models.db.element import Element, ElementInit
from app.models.element import ElementId, ElementType, TypedElementId
from app.queries.element_query import ElementQuery
from app.services.audit_service import audit
from app.services.optimistic_diff.prepare import (
    ElementStateEntry,
    OptimisticDiffPrepare,
)
from speedup import split_typed_element_id, typed_element_id


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

        conn = prepare.conn

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
        await _check_elements_unreferenced(conn, prepare)

        # Process elements and changeset updates
        created_at = await _update_elements(conn, prepare)
        await _update_changeset(conn, prepare, created_at)

        # Build result mapping
        result: dict[TypedElementId, tuple[TypedElementId, list[int]]] = {}

        for element in prepare.apply_elements:
            assigned_tid = element['typed_id']
            unassigned_tid = element.get('unassigned_typed_id', assigned_tid)
            version = element['version']

            entry = result.get(unassigned_tid)
            if entry is not None:
                entry[1].append(version)
                continue

            # Lookup negative ids in the assigned map.
            result[unassigned_tid] = (assigned_tid, [version])

        return result


async def _check_elements_unreferenced(
    conn: AsyncConnection,
    prepare: OptimisticDiffPrepare,
) -> None:
    """Check if the elements are currently unreferenced."""
    if not prepare.reference_check_element_refs:
        return

    if not await ElementQuery.check_is_unreferenced(
        conn,
        list(prepare.reference_check_element_refs),
        prepare.at_sequence_id,
    ):
        raise OptimisticDiffError('Element is referenced')


async def _update_changeset(
    conn: AsyncConnection, prepare: OptimisticDiffPrepare, now: datetime
) -> None:
    """Update the changeset table."""
    changeset = prepare.changeset
    changeset_id = changeset['id']
    closed_at = now if 'size_limit_reached' in changeset else None
    updated_at = now

    await conn.execute(
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
        WHERE id = %s
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
        ),
    )

    # Update the changeset bounds
    # It's not possible for bounds to switch from MultiPolygon to None.
    bounds = changeset.get('bounds')
    if bounds is None:
        return

    await conn.execute(
        """
        WITH new_bounds AS (
            -- Extract individual polygons from the MultiPolygon
            SELECT (ST_Dump(ST_QuantizeCoordinates(%(bounds)s, 7))).geom AS bounds
        ),
        to_delete AS (
            -- Delete bounds that no longer exist in new set
            DELETE FROM changeset_bounds cb
            WHERE changeset_id = %(changeset_id)s
              AND NOT EXISTS (
                SELECT 1 FROM new_bounds nb
                WHERE cb.bounds ~= nb.bounds
              )
        )
        -- Insert bounds that don't exist yet
        INSERT INTO changeset_bounds (changeset_id, bounds)
        SELECT %(changeset_id)s, bounds
        FROM new_bounds nb
        WHERE NOT EXISTS (
            SELECT 1 FROM changeset_bounds cb
            WHERE cb.changeset_id = %(changeset_id)s
              AND cb.bounds ~= nb.bounds
        )
        """,
        {'changeset_id': changeset_id, 'bounds': bounds},
    )


async def _update_elements(
    conn: AsyncConnection,
    prepare: OptimisticDiffPrepare,
) -> datetime:
    """Update the element table by creating new revisions."""
    (
        current_sequence_id,
        current_node_id,
        current_way_id,
        current_relation_id,
    ) = await ElementQuery.get_current_ids(conn)

    first_sequence_id = current_sequence_id + 1
    current_id_map: dict[ElementType, ElementId] = {
        'node': current_node_id,
        'way': current_way_id,
        'relation': current_relation_id,
    }

    elements: list[Element] = []
    prev_map: dict[TypedElementId, Element] = {}
    assigned_tid_map: dict[TypedElementId, TypedElementId] = {}

    # This compiled check is slightly misleading.
    # Cython will always use the first declaration.
    if cython.compiled:
        element: dict  # type: ignore
        element_init: dict  # type: ignore
    else:
        element: Element
        element_init: ElementInit

    # Process elements and prepare data for insert
    for sequence_id, element_init in enumerate(
        prepare.apply_elements, first_sequence_id
    ):
        element = element_init  # type: ignore
        element['sequence_id'] = sequence_id  # type: ignore
        element['latest'] = True
        elements.append(element)
        tid = element['typed_id']

        # Assign ids for new elements
        if 'unassigned_typed_id' in element:
            assigned_tid = assigned_tid_map.get(tid)
            if assigned_tid is not None:
                tid = assigned_tid
            else:
                # Assign a new id
                element_type = split_typed_element_id(tid)[0]
                new_id: ElementId = current_id_map[element_type] + 1  # type: ignore
                current_id_map[element_type] = new_id
                original_tid = tid
                tid = typed_element_id(element_type, new_id)
                assigned_tid_map[original_tid] = tid
            element['typed_id'] = tid

        # Update the latest flag for changed elements (local)
        prev = prev_map.get(tid)
        if prev is not None:
            prev['latest'] = False
        prev_map[tid] = element

    # Update members with assigned ids
    for element in elements:
        if (indices := element.get('unassigned_member_indices')) is not None:
            members: list[TypedElementId] = element['members'].copy()  # type: ignore
            for i in indices:
                members[i] = assigned_tid_map[members[i]]
            element['members'] = members

    await _update_latest_elements(conn, prepare.element_state)
    await _copy_elements(conn, elements)

    # Get the timestamp from an inserted element
    async with await conn.execute(
        """
        SELECT created_at FROM element
        WHERE sequence_id = %s
        """,
        (first_sequence_id,),
    ) as r:
        (created_at,) = await r.fetchone()  # type: ignore

    return created_at


async def _update_latest_elements(
    conn: AsyncConnection, element_state: dict[TypedElementId, ElementStateEntry]
) -> None:
    """Update the latest flag for changed elements (remote)."""
    typed_ids: list[TypedElementId] = []
    versions: list[int] = []

    for typed_id, entry in element_state.items():
        if entry.remote is not None:
            typed_ids.append(typed_id)
            versions.append(entry.remote['version'])

    if not typed_ids:
        return

    result = await conn.execute(
        """
        UPDATE element e SET latest = FALSE
        FROM UNNEST(%s::bigint[], %s::bigint[]) AS v(typed_id, version)
        WHERE e.typed_id = v.typed_id
          AND e.version = v.version
          AND e.latest
        """,
        (typed_ids, versions),
    )
    if result.rowcount != len(typed_ids):
        raise OptimisticDiffError('Element is outdated')


async def _copy_elements(conn: AsyncConnection, elements: list[Element]) -> None:
    async with conn.cursor().copy("""
        COPY element (
            sequence_id, changeset_id,
            typed_id, version, latest,
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
