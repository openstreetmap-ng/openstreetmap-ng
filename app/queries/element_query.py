from asyncio import TaskGroup
from string.templatelib import Template
from typing import Literal, assert_never

from psycopg import AsyncConnection, IsolationLevel
from shapely.geometry.base import BaseGeometry

from app.config import MAP_QUERY_LEGACY_NODES_LIMIT
from app.db import (
    db,
    db_fetchall,
    db_fetchcol,
    db_fetchrow,
    db_fetchrows,
    db_fetchval,
    t_and,
    t_order,
)
from app.exceptions.context import raise_for
from app.models.db.element import Element
from app.models.element import (
    TYPED_ELEMENT_ID_NODE_MAX,
    TYPED_ELEMENT_ID_RELATION_MIN,
    TYPED_ELEMENT_ID_WAY_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
    ElementId,
    TypedElementId,
)
from app.models.proto.shared_types import ElementType
from app.models.types import ChangesetId, SequenceId
from speedup import element_id


class ElementQuery:
    @staticmethod
    async def get_current_sequence_id(
        conn: AsyncConnection | None = None,
    ) -> SequenceId:
        """
        Get the current sequence id.
        Returns 0 if no elements exist.
        """
        result = await db_fetchval(
            SequenceId,
            t'SELECT COALESCE(MAX(sequence_id), 0) FROM element',
            conn=conn,
        )
        assert result is not None
        return result

    @staticmethod
    async def get_current_ids(
        conn: AsyncConnection | None = None,
    ) -> tuple[SequenceId, ElementId, ElementId, ElementId]:
        """
        Get current sequence_id and max element IDs in a single query.
        Returns (sequence_id, node_id, way_id, relation_id). Returns 0 for missing types.
        """
        row = await db_fetchrow(
            t"""
                SELECT
                    (SELECT COALESCE(MAX(sequence_id), 0) FROM element),
                    (SELECT COALESCE(MAX(typed_id), 0) FROM element WHERE typed_id <= {TYPED_ELEMENT_ID_NODE_MAX}),
                    (SELECT COALESCE(MAX(typed_id), 0) FROM element WHERE typed_id BETWEEN {TYPED_ELEMENT_ID_WAY_MIN} AND {TYPED_ELEMENT_ID_WAY_MAX}),
                    (SELECT COALESCE(MAX(typed_id), 0) FROM element WHERE typed_id >= {TYPED_ELEMENT_ID_RELATION_MIN})
            """,
            conn=conn,
        )
        assert row is not None
        seq_id, node_typed, way_typed, rel_typed = row
        return (
            seq_id,
            element_id(node_typed),
            element_id(way_typed),
            element_id(rel_typed),
        )

    @staticmethod
    async def check_is_latest(versioned_refs: list[tuple[TypedElementId, int]]):
        """Check if the given elements are currently up to date."""
        if not versioned_refs:
            return True

        ref_typed_ids = [ref[0] for ref in versioned_refs]
        ref_versions = [ref[1] for ref in versioned_refs]
        return (
            await db_fetchval(
                int,
                t"""
                    SELECT 1
                    FROM UNNEST({ref_typed_ids}::bigint[], {ref_versions}::bigint[]) AS v(typed_id, version)
                    WHERE EXISTS (
                        SELECT 1 FROM element
                        WHERE typed_id = v.typed_id
                          AND version > v.version
                    )
                    LIMIT 1
                """,
            )
        ) is None

    @staticmethod
    async def check_is_unreferenced(
        conn: AsyncConnection,
        members: list[TypedElementId],
        after_sequence_id: SequenceId,
    ):
        """Check if the given elements are currently unreferenced."""
        if not members:
            return True

        return (
            await db_fetchval(
                int,
                t"""
                    SELECT 1 FROM element
                    WHERE sequence_id > {after_sequence_id}
                    AND members && {members}::bigint[]
                    AND typed_id >= 1152921504606846976
                    AND latest
                    LIMIT 1
                """,
                conn=conn,
            )
        ) is None

    @staticmethod
    async def filter_hidden_refs(
        typed_ids: list[TypedElementId],
        *,
        at_sequence_id: SequenceId | None = None,
    ) -> list[TypedElementId]:
        """Filter the given element refs to only include hidden elements."""
        if not typed_ids:
            return []

        filters: list[Template] = [t'typed_id = v.typed_id']

        if at_sequence_id is not None:
            filters.append(t'sequence_id <= {at_sequence_id}')

        where = t_and(*filters)

        return await db_fetchcol(
            TypedElementId,
            t"""
                SELECT typed_id
                FROM UNNEST({typed_ids}::bigint[]) AS v(typed_id)
                WHERE NOT EXISTS (
                    SELECT 1 FROM (
                        SELECT visible FROM element
                        WHERE {where:q}
                        ORDER BY sequence_id DESC
                        LIMIT 1
                    )
                    WHERE visible
                )
            """,
        )

    @staticmethod
    async def map_refs_to_current_versions(
        typed_ids: list[TypedElementId],
        *,
        at_sequence_id: SequenceId | None = None,
    ) -> dict[TypedElementId, int]:
        """Map element refs to their current versions."""
        if not typed_ids:
            return {}

        filters: list[Template] = [t'typed_id = ANY({typed_ids})']

        if at_sequence_id is not None:
            filters.append(t'sequence_id <= {at_sequence_id}')

        where = t_and(*filters)
        # Allow for index-only scan
        order_by = t'version' if at_sequence_id is None else t'sequence_id'

        return dict(
            await db_fetchrows(t"""
                SELECT DISTINCT ON (typed_id) typed_id, version
                FROM element
                WHERE {where:q}
                ORDER BY typed_id DESC, {order_by:q} DESC
            """)
        )

    @staticmethod
    async def find_versions_by_ref(
        typed_id: TypedElementId,
        *,
        at_sequence_id: SequenceId | None = None,
        version_range: tuple[int, int] | None = None,
        sort_dir: Literal['asc', 'desc'] = 'asc',
        limit: int | None = None,
    ) -> list[Element]:
        """Get versions by the given element ref."""
        sort_by: Literal['sequence_id', 'version'] = 'sequence_id'
        filters: list[Template] = [t'typed_id = {typed_id}']

        if at_sequence_id is not None:
            filters.append(t'sequence_id <= {at_sequence_id}')

        if version_range is not None:
            # Switch to version ordering when filtering by version range
            # Changes nothing but enables more efficient query
            sort_by = 'version'
            v_lo, v_hi = version_range
            filters.append(t'version BETWEEN {v_lo} AND {v_hi}')

        where = t_and(*filters)
        order_dir = t_order(sort_dir)

        return await db_fetchall(
            Element,
            t"""
                SELECT * FROM element
                WHERE {where:q}
                ORDER BY {sort_by:i} {order_dir:q}
            """,
            limit=limit,
        )

    @staticmethod
    async def find_by_versioned_refs(
        versioned_refs: list[tuple[TypedElementId, int]],
        *,
        at_sequence_id: SequenceId | None = None,
        limit: int | None = None,
    ) -> list[Element]:
        """Get elements by the versioned refs."""
        if not versioned_refs:
            return []

        ref_typed_ids = [ref[0] for ref in versioned_refs]
        ref_versions = [ref[1] for ref in versioned_refs]

        filters: list[Template] = []
        if at_sequence_id is not None:
            filters.append(t'e.sequence_id <= {at_sequence_id}')

        where_sql = t_and(*filters)
        where_clause = t'WHERE {where_sql:q}' if filters else t''

        return await db_fetchall(
            Element,
            t"""
                SELECT e.* FROM element e
                JOIN UNNEST({ref_typed_ids}::bigint[], {ref_versions}::bigint[]) AS v(typed_id, version)
                  ON e.typed_id = v.typed_id AND e.version = v.version
                {where_clause:q}
            """,
            limit=limit,
        )

    @staticmethod
    async def find_by_refs(
        typed_ids: list[TypedElementId] | None,
        *,
        at_sequence_id: SequenceId | None = None,
        skip_typed_ids: list[TypedElementId] | None = None,
        recurse_ways: bool = False,
        sort_dir: Literal['asc', 'desc'] = 'desc',
        limit: int | None = None,
        TYPED_ELEMENT_ID_WAY_MIN=TYPED_ELEMENT_ID_WAY_MIN,
        TYPED_ELEMENT_ID_WAY_MAX=TYPED_ELEMENT_ID_WAY_MAX,
    ) -> list[Element]:
        """Get current elements by their element refs. Optionally recurse ways to get their nodes."""
        if not typed_ids:
            return []

        filters: list[Template] = [t'typed_id = ANY({typed_ids})']

        if at_sequence_id is not None:
            filters.append(t'sequence_id <= {at_sequence_id}')

        if skip_typed_ids is not None:
            filters.append(t'typed_id != ALL({skip_typed_ids})')

        where = t_and(*filters)
        order_dir = t_order(sort_dir)

        result = await db_fetchall(
            Element,
            t"""
                SELECT DISTINCT ON (typed_id) *
                FROM element
                WHERE {where:q}
                ORDER BY typed_id {order_dir:q}, sequence_id DESC
            """,
            limit=limit,
        )

        # Return if not recursing or reached the limit
        if not recurse_ways or (limit is not None and len(result) >= limit):
            return result

        node_typed_ids = {
            member
            for e in result
            if (members := e.get('members'))
            and TYPED_ELEMENT_ID_WAY_MIN <= e['typed_id'] <= TYPED_ELEMENT_ID_WAY_MAX
            for member in members
        }

        # Remove node typed_ids we already have
        node_typed_ids.difference_update(typed_ids)
        if not node_typed_ids:
            return result

        node_ids = list(node_typed_ids)
        node_filters: list[Template] = [t'typed_id = ANY({node_ids})']

        if at_sequence_id is not None:
            node_filters.append(t'sequence_id <= {at_sequence_id}')

        node_where = t_and(*node_filters)
        node_limit = limit - len(result) if limit is not None else None

        result.extend(
            await db_fetchall(
                Element,
                t"""
                    SELECT DISTINCT ON (typed_id) *
                    FROM element
                    WHERE {node_where:q}
                    ORDER BY typed_id {order_dir:q}, sequence_id DESC
                """,
                limit=node_limit,
            )
        )
        return result

    @staticmethod
    async def find_by_any_refs(
        refs: list[TypedElementId | tuple[TypedElementId, int]],
        *,
        at_sequence_id: SequenceId | None = None,
        limit: int | None = None,
    ) -> list[Element | None]:
        """
        Get elements by the versioned or element refs.
        Results are returned in the same order as the refs but the duplicates are skipped.
        """
        if not refs:
            return []

        # Get current sequence id if not provided
        if at_sequence_id is None:
            at_sequence_id = await ElementQuery.get_current_sequence_id()

        # Separate versioned refs from element refs
        typed_ids: list[TypedElementId] = []
        versioned_refs: list[tuple[TypedElementId, int]] = []

        for ref in refs:
            if isinstance(ref, int):
                typed_ids.append(ref)
            else:
                versioned_refs.append(ref)

        # Fetch elements in parallel
        elements_by_ref: dict[TypedElementId | tuple[TypedElementId, int], Element] = {}

        async with TaskGroup() as tg:
            typed_task = tg.create_task(
                ElementQuery.find_by_refs(
                    typed_ids,
                    at_sequence_id=at_sequence_id,
                    limit=limit,
                )
            )
            versioned_task = tg.create_task(
                ElementQuery.find_by_versioned_refs(
                    versioned_refs,
                    at_sequence_id=at_sequence_id,
                    limit=limit,
                )
            )

        for element in typed_task.result():
            elements_by_ref[element['typed_id']] = element
        for element in versioned_task.result():
            elements_by_ref[element['typed_id'], element['version']] = element

        # Prepare results in the same order as input refs, avoiding duplicates
        result_set = set[SequenceId]()
        result: list[Element | None] = []

        for ref in refs:
            element = elements_by_ref.get(ref)
            if element is None:
                result.append(None)
                continue

            sequence_id = element['sequence_id']
            if sequence_id not in result_set:
                result_set.add(sequence_id)
                result.append(element)

        return result[:limit] if (limit is not None and len(result) > limit) else result

    @staticmethod
    async def find_parents_by_refs(
        members: list[TypedElementId],
        conn: AsyncConnection | None = None,
        *,
        at_sequence_id: SequenceId | None = None,
        parent_type: ElementType | None = None,
        limit: int | None = None,
    ) -> list[Element]:
        """Get elements that reference the given elements."""
        if not members or parent_type == 'node':
            return []

        assert at_sequence_id is None or (
            at_sequence_id is not None and conn is None
        ), "at_sequence_id shouldn't be used with conn"
        assert at_sequence_id is None or len(members) <= 1, (
            "at_sequence_id shouldn't be used with multiple members"
        )

        filters: list[Template] = [t'members && {members}::bigint[]']

        if at_sequence_id is not None:
            filters.append(
                t'sequence_id <= {at_sequence_id} AND (latest OR NOT latest)'
            )
            hint_sql = t'element_members_idx element_members_history_idx'
        else:
            filters.append(t'latest')
            hint_sql = t'element_members_idx'

        if parent_type is None:
            filters.append(t'typed_id >= 1152921504606846976')
        elif parent_type == 'way':
            filters.append(
                t'typed_id BETWEEN 1152921504606846976 AND 2305843009213693951'
            )
        elif parent_type == 'relation':
            filters.append(t'typed_id >= 2305843009213693952')
        else:
            assert_never(parent_type)

        where = t_and(*filters)
        distinct = t'' if at_sequence_id is None else t'DISTINCT ON (typed_id)'
        order = t'typed_id' if at_sequence_id is None else t'typed_id, sequence_id DESC'

        return await db_fetchall(
            Element,
            t"""
                /*+ BitmapScan(element {hint_sql:q}) */
                SELECT {distinct:q} *
                FROM element
                WHERE {where:q}
                ORDER BY {order:q}
            """,
            limit=limit,
            conn=conn,
        )

    @staticmethod
    async def map_refs_to_parent_refs(
        members: list[TypedElementId],
        conn: AsyncConnection,
        *,
        limit: int | None = None,
    ) -> dict[TypedElementId, set[TypedElementId]]:
        """Map element refs to the refs of elements that reference them."""
        if not members:
            return {}

        rows = await db_fetchrows(
            t"""
                SELECT member, typed_id FROM (
                    SELECT typed_id, members
                    FROM element
                    WHERE /*+ BitmapScan(element element_members_idx) */
                        members && {members}::bigint[]
                        AND typed_id >= 1152921504606846976
                        AND latest
                )
                CROSS JOIN LATERAL UNNEST(members) member
                WHERE member = ANY({members})
            """,
            limit=limit,
            conn=conn,
        )
        result: dict[TypedElementId, set[TypedElementId]]
        result = {member: set() for member in members}
        for member, parent in rows:
            result[member].add(parent)
        return result

    @staticmethod
    async def find_by_changeset(
        changeset_id: ChangesetId,
        *,
        sort_by: Literal['typed_id', 'sequence_id'] = 'typed_id',
    ) -> list[Element]:
        """Get elements by the changeset id."""
        return await db_fetchall(
            Element,
            t"""
                SELECT * FROM element
                WHERE changeset_id = {changeset_id}
                ORDER BY {sort_by:i}
            """,
        )

    @staticmethod
    async def find_by_geom(
        geometry: BaseGeometry,
        *,
        partial_ways: bool = False,
        include_relations: bool = True,
        nodes_limit: int | None = None,
        legacy_nodes_limit: bool = False,
    ) -> list[Element]:
        """
        Find elements within the given geometry.

        The matching is performed on the nodes only and all related elements are returned:
        - nodes
        - nodes' ways
        - nodes' ways' nodes -- unless partial_ways
        - nodes' ways' relations -- if include_relations
        - nodes' relations -- if include_relations

        Results are deduplicated.
        """
        if legacy_nodes_limit:
            if nodes_limit != MAP_QUERY_LEGACY_NODES_LIMIT:
                raise ValueError(
                    'nodes_limit must be MAP_QUERY_NODES_LEGACY_LIMIT when legacy_nodes_limit is True'
                )
            nodes_limit += 1  # to detect limit exceeded

        async with db(isolation_level=IsolationLevel.REPEATABLE_READ) as conn:
            # Find all matching nodes within the geometry
            nodes = await db_fetchall(
                Element,
                t"""
                    SELECT * FROM element
                    WHERE typed_id <= 1152921504606846975
                    AND point && {geometry}
                    AND latest
                """,
                limit=nodes_limit,
                conn=conn,
            )
            if not nodes:
                return []

            if legacy_nodes_limit and len(nodes) > MAP_QUERY_LEGACY_NODES_LIMIT:
                raise_for.map_query_nodes_limit_exceeded()

            nodes_typed_ids = [node['typed_id'] for node in nodes]
            result_sequences: list[list[Element]] = [nodes]

            async with TaskGroup() as tg:

                async def fetch_parents(
                    typed_ids: list[TypedElementId],
                    parent_type: ElementType,
                ):
                    parents = await ElementQuery.find_parents_by_refs(
                        typed_ids, conn, parent_type=parent_type, limit=None
                    )
                    result_sequences.append(parents)
                    return parents

                async def way_task():
                    # fetch parent ways
                    ways = await fetch_parents(nodes_typed_ids, 'way')
                    if not ways:
                        return

                    # fetch ways' parent relations
                    if include_relations:
                        ways_typed_ids = [way['typed_id'] for way in ways]
                        tg.create_task(fetch_parents(ways_typed_ids, 'relation'))

                    # fetch ways' nodes
                    if partial_ways:
                        return

                    ways_nodes_typed_ids = {
                        member
                        for way in ways
                        if (members := way['members'])
                        for member in members
                    }
                    ways_nodes_typed_ids.difference_update(nodes_typed_ids)
                    ways_nodes = await ElementQuery.find_by_refs(
                        list(ways_nodes_typed_ids),
                        at_sequence_id=(
                            await ElementQuery.get_current_sequence_id(conn)
                        ),
                        limit=len(ways_nodes_typed_ids),
                    )
                    result_sequences.append(ways_nodes)

                tg.create_task(way_task())

                if include_relations:
                    tg.create_task(fetch_parents(nodes_typed_ids, 'relation'))

        # Remove duplicates and preserve order
        result_set = set[SequenceId]()
        result: list[Element] = []

        for elements in result_sequences:
            for element in elements:
                sequence_id = element['sequence_id']
                if sequence_id not in result_set:
                    result_set.add(sequence_id)
                    result.append(element)

        return result

    @staticmethod
    async def get_last_visible_sequence_id(element: Element) -> SequenceId | None:
        """Get the last sequence_id of the element, during which it was visible."""
        if element['latest']:
            return None

        typed_id = element['typed_id']
        sequence_id = element['sequence_id']
        return await db_fetchval(
            SequenceId,
            t"""
                SELECT MIN(sequence_id) - 1 FROM element
                WHERE typed_id = {typed_id} AND sequence_id > {sequence_id}
            """,
        )
