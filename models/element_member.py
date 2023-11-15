from collections.abc import Sequence

from sqlalchemy import Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

from models.element_type import ElementType
from models.str import EmptyStr255
from models.typed_element_ref import TypedElementRef


class ElementMemberRef(TypedElementRef):
    role: EmptyStr255  # TODO: check validation

    @property
    def typed_ref(self) -> TypedElementRef:
        return TypedElementRef(
            type=self.type,
            typed_id=self.typed_id,
        )

    def __hash__(self) -> int:
        return hash((super().__hash__(), self.role))


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
