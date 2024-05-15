import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import Literal

import cython
from anyio import create_task_group
from shapely.ops import BaseGeometry
from sqlalchemy import and_, func, null, or_, select, text, true

from app.db import db
from app.lib.exceptions_context import raise_for
from app.lib.options_context import apply_options_context
from app.limits import MAP_QUERY_LEGACY_NODES_LIMIT
from app.models.db.element import Element
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType


class ElementRepository:
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
    async def find_one_latest() -> Element | None:
        """
        Find the latest element (one with the highest sequence_id).
        """
        async with db() as session:
            stmt = select(Element).order_by(Element.sequence_id.desc()).limit(1)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def get_many_by_versioned_refs(
        versioned_refs: Sequence[VersionedElementRef],
        *,
        at_sequence_id: int | None = None,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get elements by the versioned refs.

        This method does not check for the existence of the given elements.
        """
        # small optimization
        if not versioned_refs:
            return ()

        async with db() as session:
            stmt = select(Element).where(
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
            stmt = apply_options_context(stmt)

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

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
                    # this is more efficient than (Element.sequence_id <= at_sequence_id)
                    # because it utilizes the index
                    (Element.next_sequence_id == null(),)
                    if at_sequence_id is None
                    else (
                        Element.sequence_id <= at_sequence_id,
                        or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id),
                    )
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
        ascending: bool = True,
        max_version: int | None = None,
        min_version: int | None = None,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get versions by the given element ref.
        """
        async with db() as session:
            stmt = select(Element)
            stmt = apply_options_context(stmt)
            where_and = [
                *((Element.sequence_id <= at_sequence_id,) if (at_sequence_id is not None) else ()),
                Element.type == element_ref.type,
                Element.id == element_ref.id,
            ]

            if max_version is not None:
                where_and.append(Element.version <= max_version)
            if min_version is not None:
                where_and.append(Element.version >= min_version)

            stmt = stmt.where(*where_and)

            if ascending:
                stmt = stmt.order_by(Element.version.asc())
            else:
                stmt = stmt.order_by(Element.version.desc())

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

        This method does not check for the existence of the given elements.
        """
        # small optimization
        if not element_refs:
            return ()

        type_id_map: dict[ElementType, set[int]] = defaultdict(set)

        for element_ref in element_refs:
            type_id_map[element_ref.type].add(element_ref.id)

        where_at_sequence_id = (
            (Element.next_sequence_id == null(),)
            if at_sequence_id is None
            else (
                Element.sequence_id <= at_sequence_id,
                or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id),
            )
        )

        async with db() as session:
            recurse_way_ids = type_id_map.get('way', ()) if recurse_ways else ()
            if recurse_way_ids:
                stmt = (
                    select(func.jsonb_path_query(Element.members, text("'$[*].id'")))
                    .where(
                        *where_at_sequence_id,
                        Element.type == 'way',
                        Element.id.in_(text(','.join(str(id) for id in recurse_way_ids))),
                    )
                    .distinct()
                )
                node_ids = (await session.scalars(stmt)).all()
                type_id_map['node'].update(node_ids)
                logging.debug('Found %d nodes for %d recurse ways', len(node_ids), len(recurse_way_ids))

            stmt = select(Element).where(
                *where_at_sequence_id,
                or_(
                    *(
                        and_(
                            Element.type == type,
                            Element.id.in_(text(','.join(str(id) for id in ids))),
                        )
                        for type, ids in type_id_map.items()
                    )
                ),
            )
            stmt = apply_options_context(stmt)

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

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
        # small optimization
        if not refs:
            return ()

        if at_sequence_id is None:
            at_sequence_id = await ElementRepository.get_current_sequence_id()

        versioned_refs: list[VersionedElementRef] = []
        element_refs: list[ElementRef] = []

        # organize refs by kind
        for ref in refs:
            if isinstance(ref, VersionedElementRef):
                versioned_refs.append(ref)
            else:
                element_refs.append(ref)

        ref_map: dict[VersionedElementRef | ElementRef, Element] = {}

        async def versioned_refs_task() -> None:
            elements = await ElementRepository.get_many_by_versioned_refs(
                versioned_refs,
                at_sequence_id=at_sequence_id,
                limit=limit,
            )
            ref_map.update((element.versioned_ref, element) for element in elements)

        async def element_refs_task() -> None:
            elements = await ElementRepository.get_many_by_refs(
                element_refs,
                at_sequence_id=at_sequence_id,
                limit=limit,
            )
            ref_map.update((element.element_ref, element) for element in elements)

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

        if limit is not None:
            return result[:limit]

        return result

    @staticmethod
    async def get_many_parents_by_refs(
        member_refs: Sequence[ElementRef],
        *,
        # use only short-lived at_sequence_id, this query will behave poorly otherwise
        at_sequence_id_shortlived: int | None = None,
        parent_type: ElementType | None = None,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get elements that reference the given elements.
        """
        # small optimization
        if not member_refs:
            return ()

        member_refs_t = tuple[tuple[ElementType, int], ...] = (
            (member_ref.type, member_ref.id)  #
            for member_ref in member_refs
        )

        only_nodes: cython.char = True
        only_ways_relations: cython.char = True

        for t in member_refs_t:
            type = t[0]

            if type != 'node':
                only_nodes = False
            if type != 'way' and type != 'relation':
                only_ways_relations = False

            if not only_nodes and not only_ways_relations:
                break

        # optimization: ways and relations can only be members of relations
        if parent_type is None and only_ways_relations:
            parent_type = 'relation'

        async with db() as session:
            stmt = select(Element)
            stmt = apply_options_context(stmt)
            where_and = [
                *(
                    (Element.next_sequence_id == null(),)
                    if at_sequence_id_shortlived is None
                    else (
                        Element.sequence_id <= at_sequence_id_shortlived,
                        or_(Element.next_sequence_id == null(), Element.next_sequence_id > at_sequence_id_shortlived),
                    ),
                ),
                Element.visible == true(),
            ]

            if parent_type is not None:
                where_and.append(Element.type == parent_type)
            else:
                # important! use of index requires way or relation type
                where_and.append(or_(Element.type == 'way', Element.type == 'relation'))

            # optimization: skip type checking for ways nodes
            if parent_type == 'way' and only_nodes:
                where_and.append(
                    or_(
                        *(
                            Element.members.op('@?')(text(f"'$[*] ? (@.id == {t[1]})'"))  #
                            for t in member_refs_t
                        ),
                    )
                )
            else:
                where_and.append(
                    or_(
                        *(
                            Element.members.op('@?')(text(f'\'$[*] ? (@.type == "{type}" && @.id == {id})\''))
                            for (type, id) in member_refs_t
                        ),
                    )
                )

            stmt = stmt.where(*where_and)

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def is_unreferenced(member_refs: Sequence[ElementRef], *, after_sequence_id: int) -> bool:
        """
        Check if the given elements are currently unreferenced.

        after_sequence_id is used as an optimization.
        """
        # small optimization
        if not member_refs:
            return ()

        async with db() as session:
            stmt = select(text('1')).where(
                Element.sequence_id < after_sequence_id,
                Element.next_sequence_id == null(),
                Element.visible == true(),
                or_(Element.type == 'way', Element.type == 'relation'),
                or_(
                    *(
                        Element.members.op('@?')(
                            text(f'\'$[*] ? (@.type == "{member_ref.type}" && @.id == {member_ref.id})\'')
                        )
                        for member_ref in member_refs
                    ),
                ),
            )
            return await session.scalar(stmt) is None

    @staticmethod
    async def get_many_by_changeset(
        changeset_id: int,
        *,
        sort_by: Literal['id', 'sequence_id'],
    ) -> Sequence[Element]:
        """
        Get elements by the changeset id.

        If sort_by_id is True, the results are sorted by id in ascending order.

        If sort_by_id is False, the results are sorted by sequence_id in ascending order.
        """
        async with db() as session:
            stmt = (
                select(Element)
                .where(Element.changeset_id == changeset_id)
                .order_by((Element.id if sort_by == 'id' else Element.sequence_id).asc())
            )
            stmt = apply_options_context(stmt)
            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_by_geom(
        geometry: BaseGeometry,
        *,
        nodes_limit: int | None,
        legacy_nodes_limit: bool = False,
    ) -> Sequence[Element]:
        """
        Find elements within the given geometry.

        The matching is performed on the nodes only and all related elements are returned:
        - nodes
        - nodes' ways
        - nodes' ways' nodes
        - nodes' ways' relations
        - nodes' relations

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
            stmt = select(Element).where(
                Element.next_sequence_id == null(),
                Element.visible == true(),
                Element.type == 'node',
                func.ST_Intersects(Element.point, func.ST_GeomFromText(geometry.wkt, 4326)),
            )
            stmt = apply_options_context(stmt)

            if nodes_limit is not None:
                stmt = stmt.limit(nodes_limit)

            nodes = (await session.scalars(stmt)).all()

        if legacy_nodes_limit and len(nodes) > MAP_QUERY_LEGACY_NODES_LIMIT:
            raise_for().map_query_nodes_limit_exceeded()

        nodes_refs = tuple(node.element_ref for node in nodes)
        result_sequences = [nodes]

        async def fetch_parents(element_refs: Sequence[ElementRef], parent_type: ElementType) -> Sequence[Element]:
            parents = await ElementRepository.get_many_parents_by_refs(
                element_refs,
                at_sequence_id_shortlived=at_sequence_id,
                parent_type=parent_type,
                limit=None,
            )
            if parents:
                result_sequences.append(parents)
            return parents

        async with create_task_group() as tg:

            async def way_task() -> None:
                # fetch parent ways
                ways = await fetch_parents(nodes_refs, 'way')
                if not ways:
                    return

                # fetch ways' parent relations
                ways_refs = tuple(way.element_ref for way in ways)
                tg.start_soon(fetch_parents, ways_refs, 'relation')

                # fetch ways' nodes
                ways_members_refs = tuple(member.element_ref for way in ways for member in way.members)
                ways_nodes = await ElementRepository.get_many_by_refs(
                    ways_members_refs,
                    at_sequence_id=at_sequence_id,
                    limit=len(ways_members_refs),
                )

                if ways_nodes:
                    result_sequences.append(ways_nodes)

            tg.start_soon(way_task)
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
