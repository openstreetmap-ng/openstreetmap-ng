from typing import Annotated, Self

from pydantic import Field, model_validator

from models.collections.element import Element
from models.element_member import ElementMember
from models.element_type import ElementType
from models.geometry import PointGeometry
from validators.eq import Eq


class ElementNode(Element):
    type: Annotated[ElementType, Eq(ElementType.node), Field(frozen=True)] = ElementType.node
    members: Annotated[tuple[ElementMember, ...], Field(frozen=True, max_length=0)] = ()
    point: Annotated[PointGeometry | None, Field(frozen=True)]

    @model_validator(mode='after')
    def validate_not_visible(self) -> Self:
        if not self.visible and self.point:
            self.point = None
        return super().validate_not_visible()
