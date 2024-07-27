from collections.abc import Sequence
from typing import Any

from pydantic import PositiveInt, model_validator

from app.limits import ELEMENT_RELATION_MEMBERS_LIMIT, ELEMENT_WAY_MEMBERS_LIMIT
from app.models.db.element_member import ElementMember
from app.models.element_ref import ElementType
from app.models.geometry import PointGeometry
from app.validators.tags import TagsValidating


class ElementValidating(TagsValidating):
    changeset_id: PositiveInt | None
    type: ElementType
    id: int
    version: PositiveInt
    visible: bool
    point: PointGeometry | None
    members: Sequence[ElementMember]

    @model_validator(mode='after')
    def validate_node(self):
        if self.type != 'node':
            return self

        if self.members:
            raise ValueError('Node cannot have members')

        return self

    @model_validator(mode='after')
    def validate_way(self):
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
    def validate_relation(self):
        if self.type != 'relation':
            return self

        if self.point is not None:
            raise ValueError('Relation cannot have coordinates')
        # TODO: 0.7
        # if self.visible and not self.members:
        #     raise ValueError('Relation must have at least one member')
        if len(self.members) > ELEMENT_RELATION_MEMBERS_LIMIT:
            raise ValueError(f'Relation cannot have more than {ELEMENT_RELATION_MEMBERS_LIMIT} members')
        if any(len(member.role) > 255 for member in self.members):
            raise ValueError('Relation member role cannot be longer than 255 characters')
        types = {'node', 'way', 'relation'}
        if any(member.type not in types for member in self.members):
            raise ValueError('Relation member type must be node, way or relation')

        return self

    # using 'before' mode to avoid conflicts with validate_assignment=True
    @model_validator(mode='before')
    @classmethod
    def validate_hidden_prepare(cls, data: dict[str, Any]):
        if data['visible']:
            return data

        data['tags'] = {}
        data['point'] = None
        data['members'] = ()
        return data

    @model_validator(mode='after')
    def validate_hidden(self):
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
