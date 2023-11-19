from collections.abc import Sequence

from sqlalchemy import Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

from models.element_member import ElementMemberRef
from models.element_type import ElementType


class ElementMemberRefType(TypeDecorator):
    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: Sequence[ElementMemberRef] | None, _: Dialect) -> Sequence[dict] | None:
        if value is None:
            return None
        return tuple(
            {
                'type': member.type.value,
                'typed_id': member.typed_id,
                'role': member.role,
            }
            for member in value
        )

    def process_result_value(self, value: Sequence[dict] | None, _: Dialect) -> Sequence[ElementMemberRef] | None:
        if value is None:
            return None
        return tuple(
            ElementMemberRef(
                type=ElementType(member['type']),
                typed_id=member['typed_id'],
                role=member['role'],
            )
            for member in value
        )
