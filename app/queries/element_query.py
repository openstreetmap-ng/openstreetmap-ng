import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import Literal

import cython
from anyio import create_task_group
from shapely.ops import BaseGeometry
from sqlalchemy import Select, and_, func, null, or_, select, text, true

from app.config import LEGACY_SEQUENCE_ID_MARGIN
from app.db import db
from app.lib.bundle import NamespaceBundle
from app.lib.exceptions_context import raise_for
from app.limits import MAP_QUERY_LEGACY_NODES_LIMIT
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.queries.element_member_query import ElementMemberQuery


class ElementQuery:
    @staticmethod
    async def get_current_sequence_id() -> int:
        """
        Get the current sequence id.

        Returns 0 if no elements exist.
        """
        async with db() as session:
            stmt = select(func.max(Element.sequence_id))
            sequence_id = await session.scalar(stmt)
            return sequence_id if (sequence_id is not None) else 0

    @staticmethod
    async def get_current_id_by_type(type: ElementType) -> int:
        """
        Get the last id for the given element type.

        Returns 0 if no elements exist with the given type.
        """
        async with db() as session:
            stmt = select(func.max(Element.id)).where(Element.type == type)
            element_id = await session.scalar(stmt)
            return element_id if (element_id is not None) else 0

    @staticmethod
    async def is_currently_member(member_refs: Sequence[ElementRef], *, after_sequence_id: int) -> bool:
        """
        Check if the given elements are currently members of any element.

        after_sequence_id is used as an optimization.
        """
        if not member_refs:
            return True

        async with db() as session:
            stmt = select(text('1')).where(
                ElementMember.sequence_id > after_sequence_id,
                or_(
                    *(
                        and_(
                            ElementMember.type == member_ref.type,
                            ElementMember.id == member_ref.id,
                        )
                        for member_ref in member_refs
                    ),
                ),
            )
            return await session.scalar(stmt) is not None

    @staticmethod
    async def get_current_version_by_ref(
        element_ref: ElementRef,
        *,
        at_sequence_id: int | None = None,
    ) -> int:
        """
        Get the current version of the element by the given element ref.

        Returns 0 if the element does not exist.
        """
        async with db() as session:
            stmt = select(func.max(Element.version)).where(
                *(
                    (
                        Element.sequence_id <= at_sequence_id,
                        or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id),
                    )
                    if at_sequence_id is not None
                    else ()
                ),
                Element.type == element_ref.type,
                Element.id == element_ref.id,
            )
            version = await session.scalar(stmt)
            return version if (version is not None) else 0

    @staticmethod
    async def get_versions_by_ref(
        element_ref: ElementRef,
        *,
        at_sequence_id: int | None = None,
        version_range: tuple[int, int] | None = None,
        sort_ascending: bool = True,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get versions by the given element ref.
        """
        async with db() as session:
            stmt = _select()
            where_and = [
                *((Element.sequence_id <= at_sequence_id,) if (at_sequence_id is not None) else ()),
                Element.type == element_ref.type,
                Element.id == element_ref.id,
            ]

            if version_range is not None:
                where_and.append(Element.version.between(*version_range))

            stmt = stmt.where(*where_and)

            if sort_ascending:
                stmt = stmt.order_by(Element.version.asc())
            else:
                stmt = stmt.order_by(Element.version.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_many_by_versioned_refs(
        versioned_refs: Sequence[VersionedElementRef],
        *,
        at_sequence_id: int | None = None,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get elements by the versioned refs.
        """
        if not versioned_refs:
            return ()

        async with db() as session:
            stmt = _select().where(
                *((Element.sequence_id <= at_sequence_id,) if (at_sequence_id is not None) else ()),
                or_(
                    *(
                        and_(
                            Element.type == versioned_ref.type,
                            Element.id == versioned_ref.id,
                            Element.version == versioned_ref.version,
                        )
                        for versioned_ref in versioned_refs
                    )
                ),
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_many_by_refs(
        element_refs: Sequence[ElementRef],
        *,
        at_sequence_id: int | None = None,
        recurse_ways: bool = False,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get current elements by their element refs.

        Optionally recurse ways to get their nodes.
        """
        if not element_refs:
            return ()

        type_id_map: dict[ElementType, set[int]] = defaultdict(set)
        for element_ref in element_refs:
            type_id_map[element_ref.type].add(element_ref.id)

        result: list[Element] = []

        async def task(type: ElementType, ids: set[int]) -> None:
            async with db() as session:
                stmt = _select().where(
                    *(
                        (Element.next_sequence_id == null(),)
                        if at_sequence_id is None
                        else (
                            Element.sequence_id <= at_sequence_id,
                            or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id),
                        )
                    ),
                    Element.type == type,
                    Element.id.in_(text(','.join(map(str, ids)))),
                )

                if limit is not None:
                    stmt = stmt.limit(limit)

                elements = (await session.scalars(stmt)).all()

                if elements:
                    result.extend(elements)

                    if type == 'way' and recurse_ways:
                        await ElementMemberQuery.resolve_members(elements)
                        node_ids = {member.id for element in elements for member in element.members}
                        node_ids.difference_update(type_id_map['node'])
                        if node_ids:
                            logging.debug('Found %d nodes for %d recurse ways', len(node_ids), len(ids))
                            await task('node', node_ids)

        async with create_task_group() as tg:
            for type, ids in type_id_map.items():
                tg.start_soon(task, type, ids)

        return result if (limit is None) else result[:limit]

    @staticmethod
    async def find_many_by_any_refs(
        refs: Sequence[VersionedElementRef | ElementRef],
        *,
        at_sequence_id: int | None = None,
        limit: int | None,
    ) -> Sequence[Element | None]:
        """
        Get elements by the versioned or element refs.

        Results are returned in the same order as the refs but the duplicates are skipped.
        """
        if not refs:
            return ()

        if at_sequence_id is None:
            at_sequence_id = await ElementQuery.get_current_sequence_id()

        # organize refs by kind
        versioned_refs: list[VersionedElementRef] = []
        element_refs: list[ElementRef] = []
        for ref in refs:
            if isinstance(ref, VersionedElementRef):
                versioned_refs.append(ref)
            else:
                element_refs.append(ref)

        ref_map: dict[VersionedElementRef | ElementRef, Element] = {}

        async def versioned_refs_task() -> None:
            elements = await ElementQuery.get_many_by_versioned_refs(
                versioned_refs,
                at_sequence_id=at_sequence_id,
                limit=limit,
            )
            ref_map.update((VersionedElementRef.from_element(element), element) for element in elements)

        async def element_refs_task() -> None:
            elements = await ElementQuery.get_many_by_refs(
                element_refs,
                at_sequence_id=at_sequence_id,
                limit=limit,
            )
            ref_map.update((ElementRef.from_element(element), element) for element in elements)

        async with create_task_group() as tg:
            if versioned_refs:
                tg.start_soon(versioned_refs_task)
            if element_refs:
                tg.start_soon(element_refs_task)

        # remove duplicates and preserve order
        result_set: set[int] = set()
        result: list[Element] = []
        for ref in refs:
            element = ref_map.get(ref)
            if element is None:
                continue
            element_sequence_id = element.sequence_id
            if element_sequence_id not in result_set:
                result_set.add(element_sequence_id)
                result.append(element)

        return result if (limit is None) else result[:limit]

    @staticmethod
    async def get_many_parents_by_refs(
        member_refs: Sequence[ElementRef],
        *,
        at_sequence_id: int | None = None,
        parent_type: ElementType | None = None,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get elements that reference the given elements.
        """
        if not member_refs:
            return ()

        type_id_map: dict[ElementType, list[int]] = defaultdict(list)
        for member_ref in member_refs:
            type_id_map[member_ref.type].append(member_ref.id)

        # only_nodes = not (type_id_map.get('way') or type_id_map.get('relation'))
        only_ways_relations = not type_id_map.get('node')

        # optimization: ways and relations can only be members of relations
        if parent_type is None and only_ways_relations:
            parent_type = 'relation'

        async with db() as session:
            # 1: find lifetime of each ref
            cte_sub = (
                select(Element.type, Element.id, Element.sequence_id, Element.next_sequence_id)
                .where(
                    *(
                        (Element.next_sequence_id == null(),)
                        if at_sequence_id is None
                        else (
                            Element.sequence_id <= at_sequence_id,
                            or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id),
                        )
                    ),
                    or_(
                        *(
                            and_(
                                Element.type == type,
                                Element.id.in_(text(','.join(map(str, ids)))),
                            )
                            for type, ids in type_id_map.items()
                        )
                    ),
                )
                .subquery()
            )
            # 2: find parents that referenced the refs during their lifetime
            cte = (
                select(ElementMember.sequence_id)
                .where(
                    ElementMember.type == cte_sub.c.type,
                    ElementMember.id == cte_sub.c.id,
                    ElementMember.sequence_id > cte_sub.c.sequence_id,
                    *(
                        (ElementMember.sequence_id < func.coalesce(cte_sub.c.next_sequence_id, at_sequence_id + 1),)
                        if at_sequence_id is not None
                        else ()
                    ),
                )
                .distinct()
                .cte()
                .prefix_with('MATERIALIZED')
            )
            # 3: filter parents that currently exist
            stmt = _select().where(
                *(
                    (Element.next_sequence_id == null(),)
                    if at_sequence_id is None
                    else (
                        Element.sequence_id <= at_sequence_id,
                        or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id),
                    )
                ),
                *(
                    (Element.type == parent_type,)
                    if parent_type is not None
                    else (or_(Element.type == 'way', Element.type == 'relation'),)
                ),
                Element.sequence_id.in_(cte),
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_many_by_changeset(
        changeset_id: int,
        *,
        sort_by: Literal['id', 'sequence_id'],
    ) -> Sequence[Element]:
        """
        Get elements by the changeset id.
        """
        async with db() as session:
            stmt = (
                _select()
                .where(Element.changeset_id == changeset_id)
                .order_by((Element.id if sort_by == 'id' else Element.sequence_id).asc())
            )
            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_by_geom(
        geometry: BaseGeometry,
        *,
        partial_ways: bool = False,
        include_relations: bool = True,
        nodes_limit: int | None,
        legacy_nodes_limit: bool = False,
    ) -> Sequence[Element]:
        """
        Find elements within the given geometry.

        The matching is performed on the nodes only and all related elements are returned:
        - nodes
        - nodes' ways
        - nodes' ways' nodes -- unless partial_ways
        - nodes' ways' relations -- if include_relations
        - nodes' relations -- if include_relations

        Results don't include duplicates.
        """
        if legacy_nodes_limit:
            if nodes_limit != MAP_QUERY_LEGACY_NODES_LIMIT:
                raise ValueError('nodes_limit must be MAP_QUERY_NODES_LEGACY_LIMIT when legacy_nodes_limit is True')
            nodes_limit += 1  # to detect limit exceeded

        # find all the matching nodes
        async with db() as session:
            await session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})

            stmt = select(func.max(Element.sequence_id))
            at_sequence_id = await session.scalar(stmt)
            if at_sequence_id is None:
                return ()

            # index stores only the current nodes
            stmt = _select().where(
                Element.next_sequence_id == null(),
                Element.visible == true(),
                Element.type == 'node',
                func.ST_Intersects(Element.point, func.ST_GeomFromText(geometry.wkt, 4326)),
            )

            if nodes_limit is not None:
                stmt = stmt.limit(nodes_limit)

            nodes = (await session.scalars(stmt)).all()

        if not nodes:
            return ()
        if legacy_nodes_limit and len(nodes) > MAP_QUERY_LEGACY_NODES_LIMIT:
            raise_for().map_query_nodes_limit_exceeded()

        nodes_refs = tuple(ElementRef.from_element(node) for node in nodes)
        result_sequences: list[Sequence[Element]] = [nodes]

        async def fetch_parents(element_refs: Sequence[ElementRef], parent_type: ElementType) -> Sequence[Element]:
            parents = await ElementQuery.get_many_parents_by_refs(
                element_refs,
                at_sequence_id=at_sequence_id,
                parent_type=parent_type,
                limit=None,
            )
            result_sequences.append(parents)
            return parents

        async with create_task_group() as tg:

            async def way_task() -> None:
                # fetch parent ways
                ways = await fetch_parents(nodes_refs, 'way')
                if not ways:
                    return

                # fetch ways' parent relations
                if include_relations:
                    ways_refs = tuple(ElementRef.from_element(way) for way in ways)
                    tg.start_soon(fetch_parents, ways_refs, 'relation')

                # fetch ways' nodes
                if not partial_ways:
                    await ElementMemberQuery.resolve_members(ways)
                    members_refs = {ElementRef.from_element(member) for way in ways for member in way.members}
                    members_refs.difference_update(nodes_refs)
                    if members_refs:
                        ways_nodes = await ElementQuery.get_many_by_refs(
                            members_refs,
                            at_sequence_id=at_sequence_id,
                            limit=len(members_refs),
                        )
                        result_sequences.append(ways_nodes)

            tg.start_soon(way_task)
            if include_relations:
                tg.start_soon(fetch_parents, nodes_refs, 'relation')

        # remove duplicates and preserve order
        result_set: set[int] = set()
        result: list[Element] = []
        for elements in result_sequences:
            for element in elements:
                element_sequence_id = element.sequence_id
                if element_sequence_id not in result_set:
                    result_set.add(element_sequence_id)
                    result.append(element)
        return result

    if LEGACY_SEQUENCE_ID_MARGIN:

        @staticmethod
        async def get_last_visible_sequence_id(element: Element) -> int:
            """
            Get the last sequence_id of the element, during which it was visible.

            This method assumes sequence_id is not strictly accurate.
            """
            async with db() as session:
                stmt = select(func.max(Element.sequence_id)).where(
                    Element.sequence_id < element.next_sequence_id,
                    Element.created_at
                    < select(Element.created_at)
                    .where(Element.sequence_id == element.next_sequence_id)
                    .scalar_subquery(),
                )
                return await session.scalar(stmt)

    else:

        @staticmethod
        async def get_last_visible_sequence_id(element: Element) -> int:
            """
            Get the last sequence_id of the element, during which it was visible.
            """
            return element.next_sequence_id - 1


@cython.cfunc
def _select() -> Select[Element]:
    bundle = NamespaceBundle(
        'element',
        Element.sequence_id,
        Element.changeset_id,
        Element.type,
        Element.id,
        Element.version,
        Element.visible,
        Element.tags,
        Element.point,
        Element.created_at,
        Element.next_sequence_id,
        extra_fields={
            'members': None,
            'user_id': None,
            'user_display_name': None,
        },
        single_entity=True,
    )
    return select(bundle)
