import logging
from asyncio import TaskGroup
from collections import defaultdict
from collections.abc import Awaitable, Collection, Iterable, Sequence
from itertools import chain
from typing import Literal

import cython
from shapely.geometry.base import BaseGeometry
from sqlalchemy import Select, and_, func, null, or_, select, text, true, union_all

from app.config import LEGACY_SEQUENCE_ID_MARGIN
from app.db import db
from app.lib.bundle import NamespaceBundle
from app.lib.exceptions_context import raise_for
from app.limits import MAP_QUERY_LEGACY_NODES_LIMIT
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element import ElementId, ElementRef, ElementType, VersionedElementRef
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
    async def get_current_ids() -> dict[ElementType, ElementId]:
        """
        Get the last id for each element type.

        Returns 0 if no elements exist with the given type.
        """
        async with db() as session:
            stmts = tuple(
                select(Element.type, Element.id)  #
                .where(Element.type == type)
                .order_by(Element.id.desc())
                .limit(1)
                for type in ('node', 'way', 'relation')
            )
            rows: Iterable[tuple[ElementType, ElementId]] = (await session.execute(union_all(*stmts))).all()  # pyright: ignore[reportAssignmentType]
            return dict(
                (
                    ('node', ElementId(0)),
                    ('way', ElementId(0)),
                    ('relation', ElementId(0)),
                    *rows,
                )
            )

    @staticmethod
    async def check_is_latest(versioned_refs: Collection[VersionedElementRef]) -> bool:
        """
        Check if the given elements are currently up-to-date.
        """
        if not versioned_refs:
            return True

        async with db() as session:
            stmt = (
                select(text('1'))
                .where(
                    Element.next_sequence_id != null(),
                    or_(
                        *(
                            and_(
                                Element.type == versioned_ref.type,
                                Element.id == versioned_ref.id,
                                Element.version == versioned_ref.version,
                            )
                            for versioned_ref in versioned_refs
                        ),
                    ),
                )
                .limit(1)
            )
            return await session.scalar(stmt) is None

    @staticmethod
    async def check_is_unreferenced(member_refs: Collection[ElementRef], after_sequence_id: int) -> bool:
        """
        Check if the given elements are currently unreferenced.

        after_sequence_id is used as an optimization.
        """
        if not member_refs:
            return True

        async with db() as session:
            stmt = (
                select(text('1'))
                .where(
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
                .limit(1)
            )
            return await session.scalar(stmt) is None

    @staticmethod
    async def filter_visible_refs(
        element_refs: Iterable[ElementRef],
        *,
        at_sequence_id: int | None = None,
    ) -> tuple[ElementRef, ...]:
        """
        Filter the given element refs to only include the visible elements.
        """
        type_id_map: dict[ElementType, set[ElementId]] = defaultdict(set)
        for element_ref in element_refs:
            type_id_map[element_ref.type].add(element_ref.id)
        if not type_id_map:
            return ()

        async with db() as session:
            stmt = select(Element.type, Element.id).where(
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
                Element.visible == true(),
            )
            rows = (await session.execute(stmt)).all()
            return tuple(ElementRef(type, id) for type, id in rows)

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
        sort: Literal['asc', 'desc'] = 'asc',
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
            stmt = stmt.order_by(Element.version.asc() if sort == 'asc' else Element.version.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_by_versioned_refs(
        versioned_refs: Collection[VersionedElementRef],
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
    async def get_by_refs(
        element_refs: Collection[ElementRef],
        *,
        at_sequence_id: int | None = None,
        recurse_ways: bool = False,
        limit: int | None,
    ) -> list[Element]:
        """
        Get current elements by their element refs.

        Optionally recurse ways to get their nodes.
        """
        if not element_refs:
            return []
        type_id_map: dict[ElementType, set[ElementId]] = defaultdict(set)
        for element_ref in element_refs:
            type_id_map[element_ref.type].add(element_ref.id)

        async def task(type: ElementType, ids: set[ElementId]) -> Iterable[Element]:
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

                if type == 'way' and recurse_ways:
                    await ElementMemberQuery.resolve_members(elements)
                    node_ids = {member.id for element in elements for member in element.members}
                    node_ids.difference_update(type_id_map['node'])
                    if node_ids:
                        logging.debug('Found %d nodes for %d recurse ways', len(node_ids), len(ids))
                        elements = chain(elements, await task('node', node_ids))

                return elements

        async with TaskGroup() as tg:
            tasks = tuple(tg.create_task(task(type, ids)) for type, ids in type_id_map.items())

        # remove duplicates
        result_set: set[int] = set()
        result: list[Element] = []
        for t in tasks:
            for element in t.result():
                element_sequence_id = element.sequence_id
                if element_sequence_id not in result_set:
                    result_set.add(element_sequence_id)
                    result.append(element)
        return result if (limit is None) else result[:limit]

    @staticmethod
    async def find_many_by_any_refs(
        refs: Collection[VersionedElementRef | ElementRef],
        *,
        at_sequence_id: int | None = None,
        limit: int | None,
    ) -> list[Element | None]:
        """
        Get elements by the versioned or element refs.

        Results are returned in the same order as the refs but the duplicates are skipped.
        """
        if not refs:
            return []
        # organize refs by kind
        versioned_refs: list[VersionedElementRef] = []
        element_refs: list[ElementRef] = []
        for ref in refs:
            if isinstance(ref, VersionedElementRef):
                versioned_refs.append(ref)
            else:
                element_refs.append(ref)
        if at_sequence_id is None:
            at_sequence_id = await ElementQuery.get_current_sequence_id()

        async with TaskGroup() as tg:
            versioned_task = tg.create_task(
                ElementQuery.get_by_versioned_refs(
                    versioned_refs,
                    at_sequence_id=at_sequence_id,
                    limit=limit,
                )
            )
            element_task = tg.create_task(
                ElementQuery.get_by_refs(
                    element_refs,
                    at_sequence_id=at_sequence_id,
                    limit=limit,
                )
            )

        ref_map = dict(
            chain(
                ((VersionedElementRef(e.type, e.id, e.version), e) for e in versioned_task.result()),
                ((ElementRef(e.type, e.id), e) for e in element_task.result()),
            )
        )

        # remove duplicates and preserve order
        result_set: set[int] = set()
        result: list[Element | None] = []
        for ref in refs:
            element = ref_map.get(ref)
            if element is None:
                result.append(None)
                continue
            element_sequence_id = element.sequence_id
            if element_sequence_id not in result_set:
                result_set.add(element_sequence_id)
                result.append(element)
        return result if (limit is None) else result[:limit]

    @staticmethod
    async def get_parents_by_refs(
        member_refs: Collection[ElementRef],
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
        type_id_map: dict[ElementType, list[ElementId]] = defaultdict(list)
        for member_ref in member_refs:
            type_id_map[member_ref.type].append(member_ref.id)
        # optimization: ways and relations can only be members of relations
        if parent_type is None and (not type_id_map.get('node')):
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
                        # redundant: Element.sequence_id <= at_sequence_id,
                        or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id),
                    )
                ),
                *(
                    (Element.type == parent_type,)
                    if parent_type is not None
                    else (or_(Element.type == 'way', Element.type == 'relation'),)
                ),
                Element.sequence_id.in_(cte.select()),
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_parents_refs_by_refs(
        member_refs: Collection[ElementRef],
        *,
        at_sequence_id: int | None = None,
        limit: int | None,
    ) -> dict[ElementRef, list[ElementRef]]:
        """
        Get elements refs that reference the given elements.
        """
        if not member_refs:
            return {}
        type_id_map: dict[ElementType, list[ElementId]] = defaultdict(list)
        for member_ref in member_refs:
            type_id_map[member_ref.type].append(member_ref.id)

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
                select(ElementMember.sequence_id, ElementMember.type, ElementMember.id)
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
            stmt = (
                select(cte.c.type, cte.c.id, Element.type, Element.id)
                .join_from(cte, Element, cte.c.sequence_id == Element.sequence_id)
                .where(
                    *(
                        (Element.next_sequence_id == null(),)
                        if at_sequence_id is None
                        else (
                            # redundant: Element.sequence_id <= at_sequence_id,
                            or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id),
                        )
                    )
                )
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            rows = (await session.execute(stmt)).all()
            result: dict[ElementRef, list[ElementRef]] = {member_ref: [] for member_ref in member_refs}
            for member_type, member_id, type, id in rows:
                result[ElementRef(member_type, member_id)].append(ElementRef(type, id))
            return result

    @staticmethod
    async def get_by_changeset(changeset_id: int, *, sort_by: Literal['id', 'sequence_id']) -> Sequence[Element]:
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
        resolve_all_members: bool = False,
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
                raise ValueError('nodes_limit must be ==MAP_QUERY_NODES_LEGACY_LIMIT when legacy_nodes_limit is True')
            nodes_limit += 1  # to detect limit exceeded

        # find all the matching nodes
        async with db() as session:
            await session.connection(execution_options={'isolation_level': 'REPEATABLE READ'})

            stmt = select(func.max(Element.sequence_id))
            at_sequence_id = await session.scalar(stmt)
            if at_sequence_id is None:
                return []

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
            return []
        if legacy_nodes_limit and len(nodes) > MAP_QUERY_LEGACY_NODES_LIMIT:
            raise_for().map_query_nodes_limit_exceeded()

        nodes_refs = tuple(ElementRef('node', node.id) for node in nodes)
        result_sequences: list[Iterable[Element]] = [nodes]

        async with TaskGroup() as tg:

            async def fetch_parents(
                element_refs: Collection[ElementRef],
                parent_type: ElementType,
            ) -> tuple[Sequence[Element], Awaitable[None] | None]:
                parents = await ElementQuery.get_parents_by_refs(
                    element_refs,
                    at_sequence_id=at_sequence_id,
                    parent_type=parent_type,
                    limit=None,
                )
                result_sequences.append(parents)
                if resolve_all_members:
                    return parents, tg.create_task(ElementMemberQuery.resolve_members(parents))
                else:
                    return parents, None

            async def way_task() -> None:
                # fetch parent ways
                ways, resolve_t = await fetch_parents(nodes_refs, 'way')

                # fetch ways' parent relations
                if include_relations:
                    ways_refs = tuple(ElementRef('way', way.id) for way in ways)
                    tg.create_task(fetch_parents(ways_refs, 'relation'))

                # fetch ways' nodes
                if not partial_ways:
                    if resolve_t is None:
                        resolve_t = ElementMemberQuery.resolve_members(ways)
                    await resolve_t
                    members_refs = {ElementRef('node', node.id) for way in ways for node in way.members}  # pyright: ignore[reportOptionalIterable]
                    members_refs.difference_update(nodes_refs)
                    ways_nodes = await ElementQuery.get_by_refs(
                        members_refs,
                        at_sequence_id=at_sequence_id,
                        limit=len(members_refs),
                    )
                    result_sequences.append(ways_nodes)

            tg.create_task(way_task())
            if include_relations:
                tg.create_task(fetch_parents(nodes_refs, 'relation'))

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

    @staticmethod
    async def get_last_visible_sequence_id(element: Element) -> int | None:
        """
        Get the last sequence_id of the element, during which it was visible.

        When LEGACY_SEQUENCE_ID_MARGIN is True, this method will assume that sequence_id is not accurate.
        """
        next_sequence_id = element.next_sequence_id
        if next_sequence_id is None:
            return None
        if not LEGACY_SEQUENCE_ID_MARGIN:
            return next_sequence_id - 1

        async with db() as session:
            stmt = select(func.max(Element.sequence_id)).where(
                Element.sequence_id < next_sequence_id,
                Element.created_at
                < select(Element.created_at).where(Element.sequence_id == next_sequence_id).scalar_subquery(),
            )
            return await session.scalar(stmt)


@cython.cfunc
def _select():
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
    result: Select[Element] = select(bundle)  # pyright: ignore
    return result
