from models.str import EmptyStr255
from models.typed_element_ref import TypedElementRef


class ElementMemberRef(TypedElementRef):
    role: EmptyStr255  # TODO: check validation

    def __hash__(self) -> int:
        return hash((super().__hash__(), self.role))
