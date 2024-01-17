from collections.abc import Sequence
from typing import Self

from pydantic import PositiveInt, model_validator

from app.limits import ELEMENT_RELATION_MAX_MEMBERS, ELEMENT_WAY_MAX_NODES
from app.models.element_member import ElementMemberRef
from app.models.element_type import ElementType
from app.models.geometry import PointGeometry
from app.models.validating.tags import TagsValidating


class ElementValidating(TagsValidating):
    user_id: PositiveInt
    changeset_id: PositiveInt | None
    type: ElementType
    typed_id: int
    version: PositiveInt
    visible: bool
    point: PointGeometry | None
    members: Sequence[ElementMemberRef]

    @model_validator(mode='after')
    def validate_node(self) -> Self:
        if self.type != ElementType.node:
            return self

        if self.members:
            raise ValueError('Node cannot have members')

        return self

    @model_validator(mode='after')
    def validate_way(self) -> Self:
        if self.type != ElementType.way:
            return self

        if self.point is not None:
            raise ValueError('Way cannot have coordinates')
        if self.visible and not self.members:
            raise ValueError('Way must have at least one member')
        if len(self.members) > ELEMENT_WAY_MAX_NODES:
            raise ValueError(f'Way cannot have more than {ELEMENT_WAY_MAX_NODES} members')
        if any(member.role for member in self.members):
            raise ValueError('Way cannot have members with roles')
        if any(member.type != ElementType.node for member in self.members):
            raise ValueError('Way cannot have non-node members')

        return self

    @model_validator(mode='after')
    def validate_relation(self) -> Self:
        if self.type != ElementType.relation:
            return self

        if self.point is not None:
            raise ValueError('Relation cannot have coordinates')
        # TODO: 0.7
        # if self.visible and not self.members:
        #     raise ValueError('Relation must have at least one member')
        if len(self.members) > ELEMENT_RELATION_MAX_MEMBERS:
            raise ValueError(f'Relation cannot have more than {ELEMENT_RELATION_MAX_MEMBERS} members')

        return self

    @model_validator(mode='after')
    def validate_not_visible(self) -> Self:
        if self.visible:
            return self

        if self.version == 1:
            raise ValueError('Element cannot be hidden on creation')

        self.tags = {}
        self.point = None
        self.members = ()

        return self
