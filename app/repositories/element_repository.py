from collections.abc import Sequence

import anyio
from shapely import Polygon
from sqlalchemy import INTEGER, and_, cast, func, null, or_, select
from sqlalchemy.dialects.postgresql import JSONPATH
from sqlalchemy.orm import load_only

from app.db import db
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.joinedload_context import get_joinedload
from app.limits import MAP_QUERY_LEGACY_NODES_LIMIT
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.models.versioned_element_ref import VersionedElementRef


class ElementRepository:
    @staticmethod
    async def get_last_id_by_type(type: ElementType) -> int:
        """
        Find the last id for the given type.

        Returns 0 if no elements exist for the given type.
        """

        async with db() as session:
            stmt = (
                select(Element)
                .options(load_only(Element.id, raiseload=True))
                .where(Element.type == type)
                .order_by(Element.id.desc())
                .limit(1)
            )

            element = await session.scalar(stmt)
            return element.id if (element is not None) else 0

    @staticmethod
    async def find_one_latest() -> Element | None:
        """
        Find the latest element (one with the highest sequence_id).
        """

        async with db() as session:
            stmt = select(Element).options(get_joinedload()).order_by(Element.sequence_id.desc()).limit(1)
            return await session.scalar(stmt)

    @staticmethod
    async def get_many_by_versioned_refs(
        versioned_refs: Sequence[VersionedElementRef],
        *,
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
            stmt = (
                select(Element)
                .options(get_joinedload())
                .where(
                    or_(
                        and_(
                            Element.type == versioned_ref.type,
                            Element.id == versioned_ref.id,
                            Element.version == versioned_ref.version,
                        )
                        for versioned_ref in versioned_refs
                    )
                )
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_many_by_element_ref(
        element_ref: ElementRef,
        *,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get elements by the element ref.

        Results are sorted by version in descending order (newest first).
        """

        async with db() as session:
            stmt = (
                select(Element)
                .options(get_joinedload())
                .where(
                    Element.type == element_ref.type,
                    Element.id == element_ref.id,
                )
                .order_by(Element.version.desc())
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_many_latest_by_element_refs(
        element_refs: Sequence[ElementRef],
        *,
        recurse_ways: bool = False,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get latest elements by their element refs.

        Optionally recurse ways to get their nodes.

        This method does not check for the existence of the given elements.
        """

        # small optimization
        if not element_refs:
            return ()

        # TODO: index
        # TODO: point in time
        point_in_time = utcnow()
        recurse_way_refs = tuple(ref for ref in element_refs if ref.type == ElementType.way) if recurse_ways else ()

        async with db() as session:
            stmt = (
                select(Element)
                .options(get_joinedload())
                .where(
                    Element.created_at <= point_in_time,
                    Element.superseded_at == null() | (Element.superseded_at > point_in_time),
                    or_(
                        and_(
                            Element.type == element_ref.type,
                            Element.id == element_ref.id,
                        )
                        for element_ref in element_refs
                    ),
                )
            )

            if recurse_way_refs:
                stmt = stmt.union(
                    select(Element)
                    .options(get_joinedload())
                    .where(
                        Element.created_at <= point_in_time,
                        Element.superseded_at == null() | (Element.superseded_at > point_in_time),
                        Element.type == ElementType.node,
                        Element.id.in_(
                            select(
                                cast(
                                    func.jsonb_path_query(Element.members, '$[*].id'),
                                    INTEGER,
                                )
                            )
                            .where(
                                Element.created_at <= point_in_time,
                                Element.superseded_at == null() | (Element.superseded_at > point_in_time),
                                Element.type == ElementType.way,
                                Element.id.in_(ref.id for ref in recurse_way_refs),
                            )
                            .subquery()
                        ),
                    )
                )

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_by_refs(
        refs: Sequence[VersionedElementRef | ElementRef],
        *,
        limit: int | None,
    ) -> Sequence[Element | None]:
        """
        Get elements by the versioned or element refs.

        Results are returned in the same order as the refs but the duplicates are skipped.
        """

        # small optimization
        if not refs:
            return ()

        versioned_refs = []
        element_refs = []

        # organize refs by kind
        for ref in refs:
            if isinstance(ref, VersionedElementRef):
                versioned_refs.append(ref)
            else:
                element_refs.append(ref)

        ref_map: dict[VersionedElementRef | ElementRef, Element] = {}

        async def versioned_refs_task() -> None:
            elements = await ElementRepository.get_many_by_versioned_refs(versioned_refs, limit=limit)
            ref_map.update((element.versioned_ref, element) for element in elements)

        async def element_refs_task() -> None:
            elements = await ElementRepository.get_many_latest_by_element_refs(element_refs, limit=limit)
            ref_map.update((element.element_ref, element) for element in elements)

        async with anyio.create_task_group() as tg:
            if versioned_refs:
                tg.start_soon(versioned_refs_task)
            if element_refs:
                tg.start_soon(element_refs_task)

        # deduplicate results and preserve order
        seen_sequence_id = set()
        result = []

        for ref in refs:
            element = ref_map.get(ref)

            if element is not None:
                if element.sequence_id in seen_sequence_id:
                    continue
                seen_sequence_id.add(element.sequence_id)

            result.append(element)

        if limit is not None:
            return result[:limit]

        return result

    @staticmethod
    async def get_many_parents_by_element_refs(
        member_refs: Sequence[ElementRef],
        parent_type: ElementType | None = None,
        *,
        after_sequence_id: int | None = None,
        limit: int | None,
    ) -> Sequence[Element]:
        """
        Get elements that reference the given elements.

        This method does not check for the existence of the given element.
        """

        # TODO: index
        # TODO: point in time
        point_in_time = utcnow()

        async with db() as session:
            stmt = (
                select(Element)
                .options(get_joinedload())
                .where(
                    Element.created_at <= point_in_time,
                    Element.superseded_at == null() | (Element.superseded_at > point_in_time),
                    or_(
                        func.jsonb_path_exists(
                            Element.members,
                            cast(
                                f'$[*] ? (@.type == "{member_ref.type.value}" && @.id == {member_ref.id})',
                                JSONPATH,
                            ),
                        )
                        for member_ref in member_refs
                    ),
                )
            )

            if parent_type is not None:
                stmt = stmt.where(Element.type == parent_type)
            if after_sequence_id is not None:
                stmt = stmt.where(Element.sequence_id > after_sequence_id)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_by_query(
        geometry: Polygon,
        *,
        nodes_limit: int | None,
        legacy_nodes_limit: bool = False,
    ) -> Sequence[Element]:
        """
        Find elements by the query.

        The matching is performed on the nodes only and all related elements are returned:
        - nodes
        - nodes' ways
        - nodes' ways' nodes
        - nodes' ways' relations
        - nodes' relations

        Results don't include duplicates.
        """

        # TODO: point in time
        point_in_time = utcnow()

        if legacy_nodes_limit:
            if nodes_limit != MAP_QUERY_LEGACY_NODES_LIMIT:
                raise ValueError('limit must be MAP_QUERY_NODES_LEGACY_LIMIT when legacy_nodes_limit is enabled')
            nodes_limit += 1  # to detect limit exceeded

        # find all the matching nodes
        async with db() as session:
            stmt = (
                select(Element)
                .options(get_joinedload())
                .where(
                    Element.created_at <= point_in_time,
                    Element.superseded_at == null() | (Element.superseded_at > point_in_time),
                    Element.type == ElementType.node,
                    func.ST_Intersects(Element.point, geometry.wkt),
                )
            )

            if nodes_limit is not None:
                stmt = stmt.limit(nodes_limit)

            nodes = (await session.scalars(stmt)).all()

        if legacy_nodes_limit and len(nodes) > MAP_QUERY_LEGACY_NODES_LIMIT:
            raise_for().map_query_nodes_limit_exceeded()

        nodes_refs = tuple(node.element_ref for node in nodes)
        result_sequences = [nodes]

        async def fetch_parents(element_refs: Sequence[ElementRef], parent_type: ElementType) -> Sequence[Element]:
            parents = await ElementRepository.get_many_parents_by_element_refs(
                element_refs,
                parent_type=parent_type,
                limit=None,
            )
            if parents:
                result_sequences.append(parents)
            return parents

        async with anyio.create_task_group() as tg:

            async def way_task() -> None:
                # fetch parent ways
                ways = await fetch_parents(nodes_refs, ElementType.way)

                if not ways:
                    return

                # fetch ways' parent relations
                ways_refs = tuple(way.element_ref for way in ways)
                tg.start_soon(fetch_parents, ways_refs, ElementType.relation)

                # fetch ways' nodes
                ways_members_refs = tuple(member.element_ref for way in ways for member in way.members)
                ways_nodes = await ElementRepository.get_many_latest_by_element_refs(
                    ways_members_refs,
                    limit=len(ways_members_refs),
                )

                if ways_nodes:
                    result_sequences.append(ways_nodes)

            tg.start_soon(way_task)
            tg.start_soon(fetch_parents, nodes_refs, ElementType.relation)

        # deduplicate results, preserving order
        return tuple({element.sequence_id: element for elements in result_sequences for element in elements}.values())
