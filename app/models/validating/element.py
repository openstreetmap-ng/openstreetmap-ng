from collections.abc import Sequence
from typing import Self

from pydantic import PositiveInt, model_validator

from app.limits import ELEMENT_RELATION_MEMBERS_LIMIT, ELEMENT_WAY_MEMBERS_LIMIT
from app.models.element_member_ref import ElementMemberRef
from app.models.element_type import ElementType
from app.models.geometry import PointGeometry
from app.models.validating.tags import TagsValidating


class ElementValidating(TagsValidating):
    changeset_id: PositiveInt | None
    type: ElementType
    id: int
    version: PositiveInt
    visible: bool
    point: PointGeometry | None
    members: Sequence[ElementMemberRef]

    @model_validator(mode='after')
    def validate_node(self) -> Self:
        if self.type != 'node':
            return self

        if self.members:
            raise ValueError('Node cannot have members')

        return self

    @model_validator(mode='after')
    def validate_way(self) -> Self:
        if self.type != 'way':
            return self

        if self.point is not None:
            raise ValueError('Way cannot have coordinates')
        if self.visible and not self.members:
            raise ValueError('Way must have at least one member')
        if len(self.members) > ELEMENT_WAY_MEMBERS_LIMIT:
            raise ValueError(f'Way cannot have more than {ELEMENT_WAY_MEMBERS_LIMIT} members')
        if any(member.role for member in self.members):
            raise ValueError('Way cannot have members with roles')
        if any(member.type != 'node' for member in self.members):
            raise ValueError('Way cannot have non-node members')

        return self

    @model_validator(mode='after')
    def validate_relation(self) -> Self:
        if self.type != 'relation':
            return self

        if self.point is not None:
            raise ValueError('Relation cannot have coordinates')
        # TODO: 0.7
        # if self.visible and not self.members:
        #     raise ValueError('Relation must have at least one member')
        if len(self.members) > ELEMENT_RELATION_MEMBERS_LIMIT:
            raise ValueError(f'Relation cannot have more than {ELEMENT_RELATION_MEMBERS_LIMIT} members')

        return self

    # using 'before' mode to avoid conflicts with validate_assignment=True
    @model_validator(mode='before')
    @classmethod
    def validate_hidden_prepare(cls, data: dict) -> dict:
        if data['visible']:
            return data

        data['tags'] = {}
        data['point'] = None
        data['members'] = ()
        return data

    @model_validator(mode='after')
    def validate_hidden(self) -> Self:
        if self.visible:
            return self

        if self.version == 1:
            raise ValueError('Element cannot be hidden on creation')
        if self.tags:
            raise ValueError('Hidden element cannot have tags')
        if self.point is not None:
            raise ValueError('Hidden element cannot have coordinates')
        if self.members:
            raise ValueError('Hidden element cannot have members')

        return self
