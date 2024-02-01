from sqlalchemy import Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

from app.models.element_member import ElementMemberRef
from app.models.element_type import ElementType


class ElementMemberRefType(TypeDecorator):
    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: list[ElementMemberRef] | None, _: Dialect) -> list[dict] | None:
        if value is None:
            return None
        return [
            {
                'type': member.type.value,
                'id': member.id,
                'role': member.role,
            }
            for member in value
        ]

    def process_result_value(self, value: list[dict] | None, _: Dialect) -> list[ElementMemberRef] | None:
        if value is None:
            return None
        return [
            ElementMemberRef(
                type=ElementType(member['type']),
                id=member['id'],
                role=member['role'],
            )
            for member in value
        ]
