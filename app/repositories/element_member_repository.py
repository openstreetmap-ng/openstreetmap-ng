from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.orm import defer, deferred

from app.db import db
from app.models.db.element import Element
from app.models.db.element_member import ElementMember


class ElementMemberRepository:
    @staticmethod
    async def resolve_members(elements: Sequence[Element]) -> None:
        """
        Resolve members for elements.
        """
        # small optimization
        if not elements:
            return

        id_members_map: dict[int, list[ElementMember]] = {}
        for element in elements:
            if element.type != 'node' and element.members is None and element.visible:
                id_members_map[element.sequence_id] = element.members = []

        # small optimization
        if not id_members_map:
            return

        async with db() as session:
            stmt = (
                select(ElementMember)
                .options(defer(ElementMember.order, raiseload=True))
                .where(ElementMember.sequence_id.in_(text(','.join(map(str, id_members_map)))))
                .order_by(ElementMember.sequence_id.asc(), ElementMember.order.asc())
            )

            members: Sequence[ElementMember] = (await session.scalars(stmt)).all()

        for member in members:
            id_members_map[member.sequence_id].append(member)
