from typing import Annotated, Self

from pydantic import Field, model_validator

from limits import (ELEMENT_RELATION_MAX_MEMBERS,
                    ELEMENT_RELATION_MAX_MEMBERS_SINCE)
from models.db.element import Element
from models.element_type import ElementType
from validators.eq import Eq


class ElementRelation(Element):
    type: Annotated[ElementType, Eq(ElementType.relation), Field(frozen=True)] = ElementType.relation

    @model_validator(mode='after')
    def validate_members(self) -> Self:
        if len(self.members) > ELEMENT_RELATION_MAX_MEMBERS and self.created_at > ELEMENT_RELATION_MAX_MEMBERS_SINCE:
            raise ValueError(f'{self.__class__.__qualname__} cannot have '
                             f'more than {ELEMENT_RELATION_MAX_MEMBERS} members')
        return self
