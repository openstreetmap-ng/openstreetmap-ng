from collections.abc import Sequence
from collections.abc import Set as AbstractSet

from sqlalchemy import INTEGER, and_, cast, func, null, or_, select
from sqlalchemy.dialects.postgresql import JSONPATH
from sqlalchemy.orm import load_only

from db import DB
from limits import FIND_LIMIT
from models.db.element import Element
from models.element_type import ElementType
from models.typed_element_ref import TypedElementRef
from utils import utcnow


class ElementService:
    @staticmethod
    async def find_one_last() -> Element | None:
        """
        Find the last created element.
        """

        async with DB() as session:
            stmt = select(Element).order_by(Element.id.desc()).limit(1)
            return await session.scalar(stmt)

    @staticmethod
    async def find_one_last_typed_id(type: ElementType) -> int:
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
    async def find_many_latest(typed_refs: AbstractSet[TypedElementRef]) -> Sequence[Element | None]:
        """
        Find the latest element (if any) for each of the given typed refs.
        """

        # small optimization
        if not typed_refs:
            return ()

        if not isinstance(typed_refs, AbstractSet):
            raise TypeError('typed_refs must be unique')

        async with DB() as session:
            stmt = select(Element).where(
                Element.id.in_(
                    select(func.max(Element.id))
                    .where(
                        or_(
                            and_(
                                Element.type == typed_ref.type,
                                Element.typed_id == typed_ref.typed_id,
                            )
                            for typed_ref in typed_refs
                        )
                    )
                    .group_by(Element.type, Element.typed_id)
                    .subquery()
                )
            )

            result = [None] * len(typed_refs)
            result_map = {typed_ref: i for i, typed_ref in enumerate(typed_refs)}

            async for element in await session.stream_scalars(stmt):
                result[result_map[element.typed_ref]] = element

            return result

    @staticmethod
    async def find_one_latest(typed_ref: TypedElementRef) -> Element | None:
        """
        Find the latest element (if any) for the given typed ref.
        """

        return await ElementService.find_many_latest({typed_ref})[0]

    @staticmethod
    async def get_referenced_by(
        member_ref: TypedElementRef,
        parent_type: ElementType | None = None,
        *,
        after: int | None = None,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Element]:
        """
        Get elements that reference the given element.
        """

        # TODO: index
        # TODO: point in time
        point_in_time = utcnow()

        async with DB() as session:
            stmt = select(Element).where(
                Element.created_at <= point_in_time,
                Element.superseded_at == null() | (Element.superseded_at > point_in_time),
                func.jsonb_path_exists(
                    Element.members,
                    cast(
                        f'$[*] ? (@.type == "{member_ref.type.value}" && @.typed_id == {member_ref.typed_id})',
                        JSONPATH,
                    ),
                ),
            )

            if parent_type is not None:
                stmt = stmt.where(Element.type == parent_type)
            if after is not None:
                stmt = stmt.where(Element.id > after)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_elements(
        typed_refs: AbstractSet[TypedElementRef],
        *,
        recurse_ways: bool = False,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Element]:
        """
        Get elements for the given typed refs.

        Optionally recurse ways to get their nodes.
        """

        # small optimization
        if not typed_refs:
            return ()

        # TODO: index
        # TODO: point in time
        point_in_time = utcnow()
        recurse_way_refs = tuple(ref for ref in typed_refs if ref.type == ElementType.way) if recurse_ways else ()

        async with DB() as session:
            stmt = select(Element).where(
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

            if recurse_way_refs:
                stmt = stmt.union(
                    select(Element).where(
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
                # proper limit on union requires subquery
                if recurse_way_refs:
                    stmt = select(Element).select_from(stmt.subquery()).limit(limit)
                else:
                    stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
