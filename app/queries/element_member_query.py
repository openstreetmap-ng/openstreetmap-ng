from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.orm import Bundle

from app.db import db
from app.models.db.element import Element
from app.models.db.element_member import ElementMember


class ElementMemberQuery:
    @staticmethod
    async def resolve_members(elements: Sequence[Element]) -> None:
        """
        Resolve members for elements.
        """
        id_members_map: dict[int, list[ElementMember]] = {}
        for element in elements:
            if element.type != 'node' and element.members is None and element.visible:
                id_members_map[element.sequence_id] = element.members = []

        # small optimization
        if not id_members_map:
            return

        async with db() as session:
            bundle = Bundle(
                'member',
                ElementMember.sequence_id,
                ElementMember.type,
                ElementMember.id,
                ElementMember.role,
                single_entity=True,
            )
            stmt = (
                select(bundle)
                .where(ElementMember.sequence_id.in_(text(','.join(map(str, id_members_map)))))
                .order_by(ElementMember.sequence_id.asc(), ElementMember.order.asc())
            )
            members = (await session.scalars(stmt)).all()

        current_sequence_id: int = 0
        current_members: list[ElementMember] = []

        for member in members:
            member_sequence_id = member.sequence_id
            if current_sequence_id != member_sequence_id:
                current_sequence_id = member_sequence_id
                current_members = id_members_map[member_sequence_id]
            current_members.append(member)
