from dataclasses import dataclass

from sqlalchemy import Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

from app.models.element_ref import ElementRef
from app.models.str import RoleStr


@dataclass(frozen=True, slots=True)
class ElementMemberRef(ElementRef):
    role: RoleStr


# ideally we would use a composite type here,
# but they are not supported by SQLAlchemy and I failed to implement it myself
class ElementMemberRefJSONB(TypeDecorator):
    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: list[ElementMemberRef] | None, _: Dialect) -> list[dict] | None:
        if value is None:
            return None
        return [
            {
                'type': member.type,
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
                type=member['type'],
                id=member['id'],
                role=member['role'],
            )
            for member in value
        ]
