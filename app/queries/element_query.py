import logging
from asyncio import TaskGroup
from contextlib import nullcontext
from typing import Any, Literal

from psycopg import AsyncConnection, IsolationLevel
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Identifier
from shapely.geometry.base import BaseGeometry

from app.config import (
    LEGACY_ALLOW_MISSING_ELEMENT_MEMBERS,
    MAP_QUERY_LEGACY_NODES_LIMIT,
)
from app.db import db
from app.lib.exceptions_context import raise_for
from app.models.db.element import Element
from app.models.element import (
    TYPED_ELEMENT_ID_NODE_MAX,
    TYPED_ELEMENT_ID_RELATION_MIN,
    TYPED_ELEMENT_ID_WAY_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
    ElementId,
    ElementType,
    TypedElementId,
)
from app.models.types import ChangesetId, SequenceId
from speedup.element_type import split_typed_element_id


class ElementQuery:
    @staticmethod
    async def get_current_sequence_id(
        conn: AsyncConnection | None = None,
    ) -> SequenceId:
        """
        Get the current sequence id.
        Returns 0 if no elements exist.
        """
        async with (
            nullcontext(conn) if conn is not None else db() as conn,  # noqa: PLR1704
            await conn.execute(
                'SELECT COALESCE(MAX(sequence_id), 0) FROM element'
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore

    @staticmethod
    async def get_current_ids() -> dict[ElementType, ElementId]:
        """
        Get the last id for each element type.
        Returns 0 if no elements exist with the given type.
        """
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT MAX(typed_id) FROM element
                WHERE typed_id <= %s
                UNION ALL
                SELECT MAX(typed_id) FROM element
                WHERE typed_id BETWEEN %s AND %s
                UNION ALL
                SELECT MAX(typed_id) FROM element
                WHERE typed_id >= %s
                """,
                (
                    TYPED_ELEMENT_ID_NODE_MAX,
                    TYPED_ELEMENT_ID_WAY_MIN,
                    TYPED_ELEMENT_ID_WAY_MAX,
                    TYPED_ELEMENT_ID_RELATION_MIN,
                ),
            ) as r,
        ):
            result: dict[ElementType, int] = {'node': 0, 'way': 0, 'relation': 0}
            typed_id: TypedElementId | None
            for (typed_id,) in await r.fetchall():
                if typed_id is not None:
                    type, id = split_typed_element_id(typed_id)
                    result[type] = id
            return result  # type: ignore

    @staticmethod
    async def check_is_latest(versioned_refs: list[tuple[TypedElementId, int]]) -> bool:
        """Check if the given elements are currently up-to-date."""
        if not versioned_refs:
            return True

        async with (
            db() as conn,
            await conn.execute(
                SQL("""
                    SELECT 1 FROM (VALUES {}) AS v(typed_id, version)
                    WHERE EXISTS (
                        SELECT 1 FROM element
                        WHERE typed_id = v.typed_id
                        AND version > v.version
                    )
                    LIMIT 1
                """).format(SQL(',').join([SQL('(%s, %s)')] * len(versioned_refs))),
                [v for ref in versioned_refs for v in ref],
            ) as r,
        ):
            return await r.fetchone() is None

    @staticmethod
    async def check_is_unreferenced(
        members: list[TypedElementId],
        after_sequence_id: SequenceId,
    ) -> bool:
        """
        Check if the given elements are currently unreferenced.
        after_sequence_id is used as an optimization.
        """
        if not members:
            return True

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT 1 FROM element
                WHERE sequence_id > %s
                AND members && %s::bigint[]
                AND typed_id >= 1152921504606846976
                AND latest
                LIMIT 1
                """,
                (after_sequence_id, members),
            ) as r,
        ):
            return await r.fetchone() is None

    @staticmethod
    async def filter_visible_refs(
        typed_ids: list[TypedElementId],
        *,
        at_sequence_id: SequenceId | None = None,
    ) -> list[TypedElementId]:
        """Filter the given element refs to only include the visible elements."""
        if not typed_ids:
            return []

        conditions: list[Composable] = [SQL('typed_id = ANY(%s)')]
        params: list[Any] = [typed_ids]

        if at_sequence_id is not None:
            conditions.append(SQL('sequence_id <= %s'))
            params.append(at_sequence_id)

        query = SQL("""
            SELECT typed_id FROM (
                SELECT DISTINCT ON (typed_id) typed_id, visible
                FROM element
                WHERE {conditions}
                ORDER BY typed_id, sequence_id DESC
            )
            WHERE visible
        """).format(conditions=SQL(' AND ').join(conditions))

        async with db() as conn, await conn.execute(query, params) as r:
            return [c for (c,) in await r.fetchall()]

    @staticmethod
    async def get_current_versions_by_refs(
        typed_ids: list[TypedElementId],
        *,
        at_sequence_id: SequenceId | None = None,
    ) -> dict[TypedElementId, int]:
        """Get the current version of the element by the given element ref."""
        if not typed_ids:
            return {}

        conditions: list[Composable] = [SQL('typed_id = ANY(%s)')]
        params: list[Any] = [typed_ids]

        if at_sequence_id is not None:
            conditions.append(SQL('sequence_id <= %s'))
            params.append(at_sequence_id)

        query = SQL("""
            SELECT DISTINCT ON (typed_id) typed_id, version
            FROM element
            WHERE {conditions}
            ORDER BY typed_id, sequence_id DESC
        """).format(conditions=SQL(' AND ').join(conditions))

        async with db() as conn, await conn.execute(query, params) as r:
            return dict(await r.fetchall())

    @staticmethod
    async def get_versions_by_ref(
        typed_id: TypedElementId,
        *,
        at_sequence_id: SequenceId | None = None,
        version_range: tuple[int, int] | None = None,
        sort_dir: Literal['asc', 'desc'] = 'asc',
        limit: int | None = None,
    ) -> list[Element]:
        """Get versions by the given element ref."""
        sort_by: Literal['sequence_id', 'version'] = 'sequence_id'
        conditions: list[Composable] = [SQL('typed_id = %s')]
        params: list[Any] = [typed_id]

        if at_sequence_id is not None:
            conditions.append(SQL('sequence_id <= %s'))
            params.append(at_sequence_id)

        if version_range is not None:
            # Switch to version ordering when filtering by version range
            # Changes nothing but enables more efficient query
            sort_by = 'version'
            conditions.append(SQL('version BETWEEN %s AND %s'))
            params.extend(version_range)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT * FROM element
            WHERE {conditions}
            ORDER BY {order_by} {order_dir}
            {limit}
        """).format(
            conditions=SQL(' AND ').join(conditions),
            order_by=Identifier(sort_by),
            order_dir=SQL(sort_dir),
            limit=limit_clause,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def get_by_versioned_refs(
        versioned_refs: list[tuple[TypedElementId, int]],
        *,
        at_sequence_id: SequenceId | None = None,
        limit: int | None = None,
    ) -> list[Element]:
        """Get elements by the versioned refs."""
        if not versioned_refs:
            return []

        conditions: list[Composable] = []
        params: list[Any] = []

        for ref in versioned_refs:
            conditions.append(SQL('(typed_id = %s AND version = %s)'))
            params.extend(ref)

        conditions = [SQL('({})').format(SQL(' OR ').join(conditions))]

        if at_sequence_id is not None:
            conditions.append(SQL('sequence_id <= %s'))
            params.append(at_sequence_id)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT * FROM element
            WHERE {conditions}
            {limit}
        """).format(
            conditions=SQL(' AND ').join(conditions),
            limit=limit_clause,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def get_by_refs(
        typed_ids: list[TypedElementId] | None,
        *,
        at_sequence_id: SequenceId | None = None,
        recurse_ways: bool = False,
        limit: int | None = None,
    ) -> list[Element]:
        """Get current elements by their element refs. Optionally recurse ways to get their nodes."""
        if not typed_ids:
            return []

        conditions: list[Composable] = [SQL('typed_id = ANY(%s)')]
        params: list[Any] = [typed_ids]

        if at_sequence_id is not None:
            conditions.append(SQL('sequence_id <= %s'))
            params.append(at_sequence_id)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT DISTINCT ON (typed_id) *
            FROM element
            WHERE {conditions}
            ORDER BY typed_id, sequence_id DESC
            {limit}
        """).format(
            conditions=SQL(' AND ').join(conditions),
            limit=limit_clause,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            result: list[Element] = await r.fetchall()  # type: ignore

        # Return if not recursing or reached the limit
        if not recurse_ways or (limit is not None and len(result) >= limit):
            return result

        typed_element_id_way_min = TYPED_ELEMENT_ID_WAY_MIN
        typed_element_id_way_max = TYPED_ELEMENT_ID_WAY_MAX
        node_typed_ids = {
            member
            for e in result
            if (members := e.get('members'))
            and typed_element_id_way_min <= e['typed_id'] <= typed_element_id_way_max
            for member in members
        }

        # Remove node typed_ids we already have
        node_typed_ids.difference_update(typed_ids)
        if not node_typed_ids:
            return result

        conditions = [SQL('typed_id = ANY(%s)')]
        params = [list(node_typed_ids)]

        if at_sequence_id is not None:
            conditions.append(SQL('sequence_id <= %s'))
            params.append(at_sequence_id)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit - len(result))
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT DISTINCT ON (typed_id) *
            FROM element
            WHERE {conditions}
            ORDER BY typed_id, sequence_id DESC
            {limit}
        """).format(
            conditions=SQL(' AND ').join(conditions),
            limit=limit_clause,
        )

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(query, params) as r,
        ):
            result.extend(await r.fetchall())  # type: ignore
            return result

    @staticmethod
    async def find_many_by_any_refs(
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
                ElementQuery.get_by_refs(
                    typed_ids,
                    at_sequence_id=at_sequence_id,
                    limit=limit,
                )
            )
            versioned_task = tg.create_task(
                ElementQuery.get_by_versioned_refs(
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
        result_set: set[SequenceId] = set()
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
    async def get_parents_by_refs(
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

        conditions: list[Composable] = [SQL('members && %s::bigint[]')]
        params: list[Any] = [members]

        if at_sequence_id is not None:
            conditions.append(SQL('sequence_id <= %s AND (latest OR NOT latest)'))
            params.append(at_sequence_id)
        else:
            conditions.append(SQL('latest'))

        if parent_type is None:
            conditions.append(SQL('typed_id >= 1152921504606846976'))
        elif parent_type == 'way':
            conditions.append(
                SQL('typed_id BETWEEN 1152921504606846976 AND 2305843009213693951')
            )
        elif parent_type == 'relation':
            conditions.append(SQL('typed_id >= 2305843009213693952'))
        else:
            raise NotImplementedError(f'Unsupported parent type {parent_type!r}')

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        # Find elements that reference the member typed_ids
        query = SQL("""
            SELECT {distinct} *
            FROM element
            WHERE {conditions}
            ORDER BY {order}
            {limit}
        """).format(
            distinct=(
                SQL('')  #
                if at_sequence_id is None
                else SQL('DISTINCT ON (typed_id)')
            ),
            conditions=SQL(' AND ').join(conditions),
            order=(
                SQL('typed_id')
                if at_sequence_id is None
                else SQL('typed_id, sequence_id DESC')
            ),
            limit=limit_clause,
        )

        async with (
            nullcontext(conn) if conn is not None else db() as conn,  # noqa: PLR1704
            conn.cursor(row_factory=dict_row) as cur,
        ):
            # The members query tends to use an incorrect index, because of skewed statistics.
            # Force disabling indexscan/seqscan to prefer using GIN bitmapscan.
            await cur.execute('SET LOCAL enable_indexscan = off')
            await cur.execute('SET LOCAL enable_seqscan = off')

            result = await (await cur.execute(query, params)).fetchall()

            await cur.execute('RESET enable_indexscan')
            await cur.execute('RESET enable_seqscan')
            return result  # type: ignore

    @staticmethod
    async def get_current_parents_refs_by_refs(
        members: list[TypedElementId],
        conn: AsyncConnection,
        *,
        limit: int | None = None,
    ) -> dict[TypedElementId, set[TypedElementId]]:
        """Get elements refs that reference the given elements."""
        if not members:
            return {}

        inner_conditions: list[Composable] = [
            SQL("""
                members && %s::bigint[]
                AND typed_id >= 1152921504606846976
                AND latest
            """)
        ]
        params: list[Any] = [members]

        outer_conditions: list[Composable] = [SQL('member = ANY(%s)')]
        params.append(members)

        if limit is not None:
            limit_clause = SQL('LIMIT %s')
            params.append(limit)
        else:
            limit_clause = SQL('')

        query = SQL("""
            SELECT member, typed_id FROM (
                SELECT typed_id, members
                FROM element
                WHERE {inner_conditions}
            )
            CROSS JOIN LATERAL UNNEST(members) member
            WHERE {outer_conditions}
            {limit}
        """).format(
            inner_conditions=SQL(' AND ').join(inner_conditions),
            outer_conditions=SQL(' AND ').join(outer_conditions),
            limit=limit_clause,
        )

        async with conn.cursor() as cur:
            # The members query tends to use an incorrect index, because of skewed statistics.
            # Force disabling indexscan/seqscan to prefer using GIN bitmapscan.
            await cur.execute('SET LOCAL enable_indexscan = off')
            await cur.execute('SET LOCAL enable_seqscan = off')

            result: dict[TypedElementId, set[TypedElementId]]
            result = {member: set() for member in members}
            for member, parent in await (await cur.execute(query, params)).fetchall():
                result[member].add(parent)

            await cur.execute('RESET enable_indexscan')
            await cur.execute('RESET enable_seqscan')
            return result

    @staticmethod
    async def get_by_changeset(
        changeset_id: ChangesetId,
        *,
        sort_by: Literal['typed_id', 'sequence_id'] = 'typed_id',
    ) -> list[Element]:
        """Get elements by the changeset id."""
        query = SQL("""
            SELECT * FROM element
            WHERE changeset_id = %s
            ORDER BY {sort_by}
        """).format(sort_by=Identifier(sort_by))

        async with (
            db() as conn,
            await conn.cursor(row_factory=dict_row).execute(
                query, (changeset_id,)
            ) as r,
        ):
            return await r.fetchall()  # type: ignore

    @staticmethod
    async def find_many_by_geom(
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
            params: list[Any] = [geometry]

            if nodes_limit is not None:
                limit_clause = SQL('LIMIT %s')
                params.append(nodes_limit)
            else:
                limit_clause = SQL('')

            query = SQL("""
                SELECT * FROM element
                WHERE typed_id <= 1152921504606846975
                AND point && %s
                AND latest
                {limit}
            """).format(limit=limit_clause)

            # Find all matching nodes within the geometry
            async with await conn.cursor(row_factory=dict_row).execute(
                query, params
            ) as r:
                nodes: list[Element] = await r.fetchall()  # type: ignore
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
                ) -> list[Element]:
                    parents = await ElementQuery.get_parents_by_refs(
                        typed_ids, conn, parent_type=parent_type, limit=None
                    )
                    result_sequences.append(parents)
                    return parents

                async def way_task() -> None:
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
                    ways_nodes = await ElementQuery.get_by_refs(
                        list(ways_nodes_typed_ids),
                        at_sequence_id=(
                            await ElementQuery.get_current_sequence_id(conn)
                        ),
                        limit=len(ways_nodes_typed_ids),
                    )
                    result_sequences.append(ways_nodes)

                    # check missing ways' nodes
                    if len(ways_nodes) == len(ways_nodes_typed_ids):
                        return

                    missing_ways_nodes_typed_ids = ways_nodes_typed_ids.difference(
                        node['typed_id'] for node in ways_nodes
                    )
                    assert LEGACY_ALLOW_MISSING_ELEMENT_MEMBERS, (
                        f'Ways have missing nodes: {missing_ways_nodes_typed_ids}'
                    )
                    for way in ways:
                        if (
                            (members := way['members'])  #
                            and not missing_ways_nodes_typed_ids.isdisjoint(members)
                        ):
                            logging.debug(
                                '%s/%dv%d has missing members',
                                *split_typed_element_id(way['typed_id']),
                                way['version'],
                            )
                            way['members'] = [
                                member
                                for member in members
                                if member not in missing_ways_nodes_typed_ids
                            ]

                tg.create_task(way_task())

                if include_relations:
                    tg.create_task(fetch_parents(nodes_typed_ids, 'relation'))

        # Remove duplicates and preserve order
        result_set: set[SequenceId] = set()
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

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT MIN(sequence_id) - 1 FROM element
                WHERE typed_id = %s AND sequence_id > %s
                """,
                (element['typed_id'], element['sequence_id']),
            ) as r,
        ):
            return (await r.fetchone())[0]  # type: ignore
