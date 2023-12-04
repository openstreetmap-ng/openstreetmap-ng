from collections.abc import Sequence
from itertools import islice

import anyio
from shapely import Polygon
from sqlalchemy import INTEGER, and_, cast, func, null, or_, select
from sqlalchemy.dialects.postgresql import JSONPATH
from sqlalchemy.orm import load_only

from db import DB
from lib.exceptions import raise_for
from lib.joinedload_context import get_joinedload
from limits import FIND_LIMIT, MAP_QUERY_LEGACY_NODES_LIMIT
from models.db.element import Element
from models.element_type import ElementType
from models.typed_element_ref import TypedElementRef
from models.versioned_element_ref import VersionedElementRef
from utils import utcnow


class ElementRepository:
    @staticmethod
    async def get_last_typed_id_by_type(type: ElementType) -> int:
        """
        Find the last typed_id for the given type.

        Returns 0 if no elements exist for the given type.
        """

        async with DB() as session:
            stmt = (
                select(Element)
                .options(load_only(Element.typed_id, raiseload=True))
                .where(Element.type == type)
                .order_by(Element.typed_id.desc())
                .limit(1)
            )

            element = await session.scalar(stmt)
            return element.typed_id if element else 0

    @staticmethod
    async def find_one_latest() -> Element | None:
        """
        Find the latest element.
        """

        async with DB() as session:
            stmt = select(Element).options(get_joinedload()).order_by(Element.id.desc()).limit(1)
            return await session.scalar(stmt)

    @staticmethod
    async def get_many_by_versioned_refs(
        versioned_refs: Sequence[VersionedElementRef],
        *,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Element]:
        """
        Get elements by the versioned refs.

        This method does not check for the existence of the given elements.
        """

        # small optimization
        if not versioned_refs:
            return ()

        async with DB() as session:
            stmt = (
                select(Element)
                .options(get_joinedload())
                .where(
                    or_(
                        and_(
                            Element.type == versioned_ref.type,
                            Element.typed_id == versioned_ref.typed_id,
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
    async def get_many_by_typed_ref(
        typed_ref: TypedElementRef,
        *,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Element]:
        """
        Get elements by the typed ref.
        """

        async with DB() as session:
            stmt = (
                select(Element)
                .options(get_joinedload())
                .where(
                    Element.type == typed_ref.type,
                    Element.typed_id == typed_ref.typed_id,
                )
                .order_by(Element.version.desc())
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_many_latest_by_typed_refs(
        typed_refs: Sequence[TypedElementRef],
        *,
        recurse_ways: bool = False,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Element]:
        """
        Get elements by the typed refs.

        Optionally recurse ways to get their nodes.

        This method does not check for the existence of the given elements.
        """

        # small optimization
        if not typed_refs:
            return ()

        # TODO: index
        # TODO: point in time
        point_in_time = utcnow()
        recurse_way_refs = tuple(ref for ref in typed_refs if ref.type == ElementType.way) if recurse_ways else ()

        async with DB() as session:
            stmt = (
                select(Element)
                .options(get_joinedload())
                .where(
                    Element.created_at <= point_in_time,
                    Element.superseded_at == null() | (Element.superseded_at > point_in_time),
                    or_(
                        and_(
                            Element.type == typed_ref.type,
                            Element.typed_id == typed_ref.typed_id,
                        )
                        for typed_ref in typed_refs
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
                        Element.typed_id.in_(
                            select(
                                cast(
                                    func.jsonb_path_query(Element.members, '$[*].typed_id'),
                                    INTEGER,
                                )
                            )
                            .where(
                                Element.created_at <= point_in_time,
                                Element.superseded_at == null() | (Element.superseded_at > point_in_time),
                                Element.type == ElementType.way,
                                Element.typed_id.in_(ref.typed_id for ref in recurse_way_refs),
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
        refs: Sequence[VersionedElementRef | TypedElementRef],
        *,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Element | None]:
        """
        Get elements by the ref strings.

        Results are ordered by the given type_strs and don't include duplicates.
        """

        # small optimization
        if not refs:
            return ()

        versioned_refs = []
        typed_refs = []

        for ref in refs:
            if isinstance(ref, VersionedElementRef):
                versioned_refs.append(ref)
            else:
                typed_refs.append(ref)

        ref_map: dict[VersionedElementRef | TypedElementRef, Element] = {}

        async def versioned_task() -> None:
            elements = await ElementRepository.get_many_by_versioned_refs(versioned_refs, limit=limit)
            ref_map.update((element.versioned_ref, element) for element in elements)

        async def typed_task() -> None:
            elements = await ElementRepository.get_many_latest_by_typed_refs(typed_refs, limit=limit)
            ref_map.update((element.typed_ref, element) for element in elements)

        async with anyio.create_task_group() as tg:
            if versioned_refs:
                tg.start_soon(versioned_task)
            if typed_refs:
                tg.start_soon(typed_task)

        # efficiently deduplicate results, preserving order
        def result_d_gen():
            for i, ref in enumerate(refs):
                element = ref_map.get(ref)
                yield (element.id, element) if element else (-i, None)

        result_d = dict(result_d_gen()).values()

        if limit is not None:  # noqa: SIM108
            result = tuple(islice(result_d, limit))
        else:
            result = tuple(result_d)

        return result

    @staticmethod
    async def get_many_parents_by_typed_refs(
        member_refs: Sequence[TypedElementRef],
        parent_type: ElementType | None = None,
        *,
        after: int | None = None,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Element]:
        """
        Get elements that reference the given elements.

        This method does not check for the existence of the given element.
        """

        # TODO: index
        # TODO: point in time
        point_in_time = utcnow()

        async with DB() as session:
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
                                f'$[*] ? (@.type == "{member_ref.type.value}" && @.typed_id == {member_ref.typed_id})',
                                JSONPATH,
                            ),
                        )
                        for member_ref in member_refs
                    ),
                )
            )

            if parent_type is not None:
                stmt = stmt.where(Element.type == parent_type)
            if after is not None:
                stmt = stmt.where(Element.id > after)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_by_query(
        geometry: Polygon,
        *,
        nodes_limit: int | None = FIND_LIMIT,
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
            nodes_limit += 1

        # find all the matching nodes
        async with DB() as session:
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

        nodes_typed_refs = tuple(node.typed_ref for node in nodes)
        result_sequences = [nodes]

        async def fetch_parents(typed_refs: Sequence[TypedElementRef], parent_type: ElementType) -> Sequence[Element]:
            parents = await ElementRepository.get_many_parents_by_typed_refs(
                typed_refs,
                parent_type=parent_type,
                limit=None,
            )
            if parents:
                result_sequences.append(parents)
            return parents

        async with anyio.create_task_group() as tg:

            async def way_task() -> None:
                # fetch parent ways
                ways = await fetch_parents(nodes_typed_refs, ElementType.way)

                if not ways:
                    return

                # fetch ways' parent relations
                ways_typed_refs = tuple(way.typed_ref for way in ways)
                tg.start_soon(fetch_parents, ways_typed_refs, ElementType.relation)

                # fetch ways' nodes
                ways_member_refs = tuple(member.typed_ref for way in ways for member in way.members)
                ways_nodes = await ElementRepository.get_many_latest_by_typed_refs(
                    ways_member_refs,
                    limit=None,
                )

                if ways_nodes:
                    result_sequences.append(ways_nodes)

            tg.start_soon(way_task)
            tg.start_soon(fetch_parents, nodes_typed_refs, ElementType.relation)

        # deduplicate results, preserving order
        return tuple({element.id: element for elements in result_sequences for element in elements}.values())
