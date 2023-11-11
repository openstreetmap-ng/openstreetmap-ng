from typing import Annotated, Self

from pydantic import Field, model_validator

from limits import ELEMENT_WAY_MAX_NODES, ELEMENT_WAY_MAX_NODES_SINCE
from models.db.element import Element
from models.element_type import ElementType
from validators.eq import Eq


class ElementWay(Element):
    type: Annotated[ElementType, Eq(ElementType.way), Field(frozen=True)] = ElementType.way

    @model_validator(mode='after')
    def validate_members(self) -> Self:
        if self.visible and not self.members:
            raise ValueError(f'{self.__class__.__qualname__} must have at least one node')
        if len(self.members) > ELEMENT_WAY_MAX_NODES and self.created_at > ELEMENT_WAY_MAX_NODES_SINCE:
            raise ValueError(f'{self.__class__.__qualname__} cannot have more than {ELEMENT_WAY_MAX_NODES} nodes')
        if any(member.role for member in self.members):
            raise ValueError(f'{self.__class__.__qualname__} cannot have members with roles')
        if any(member.ref.type != ElementType.node for member in self.members):
            raise ValueError(f'{self.__class__.__qualname__} cannot have non-node members')
        return self
