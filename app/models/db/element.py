from datetime import datetime
from typing import Annotated, Literal, NewType, NotRequired, TypedDict

import cython
import numpy as np
from annotated_types import MaxLen, MinLen
from pydantic import PositiveInt, TypeAdapter
from shapely import Point

from app.config import PYDANTIC_CONFIG
from app.limits import ELEMENT_RELATION_MEMBERS_LIMIT, ELEMENT_WAY_MEMBERS_LIMIT, TAGS_KEY_MAX_LENGTH
from app.models.db.changeset import ChangesetId
from app.models.db.user import UserDisplay, UserId
from app.models.element import TYPED_ELEMENT_ID_NODE_MAX, TypedElementId, split_typed_element_id
from app.validators.geometry import GeometryValidator
from app.validators.tags import TagsValidating
from app.validators.unicode import UnicodeValidator
from app.validators.xml import XMLSafeValidator

SequenceId = NewType('SequenceId', int)


class ElementInit(TypedDict):
    changeset_id: ChangesetId | None
    typed_id: TypedElementId
    version: PositiveInt
    visible: bool
    tags: TagsValidating | None
    point: Annotated[Point, GeometryValidator] | None
    members: list[TypedElementId] | None
    members_roles: (
        list[
            Annotated[
                str,
                UnicodeValidator,
                MinLen(1),
                MaxLen(TAGS_KEY_MAX_LENGTH),
                XMLSafeValidator,
            ]
        ]
        | None
    )

    # runtime
    delete_if_unused: NotRequired[Literal[True]]


class Element(ElementInit):
    sequence_id: SequenceId
    next_sequence_id: SequenceId | None
    created_at: datetime

    # runtime
    user_id: NotRequired[UserId]
    user: NotRequired[UserDisplay]


_ElementInitListValidator = TypeAdapter(list[ElementInit], config=PYDANTIC_CONFIG)


def validate_elements(elements: list[ElementInit]) -> list[ElementInit]:
    elements = _ElementInitListValidator.validate_python(elements)

    for element in elements:
        type = split_typed_element_id(element['typed_id'])[0]
        if type == 'node':
            _validate_node(element)
        elif type == 'way':
            _validate_way(element)
        elif type == 'relation':
            _validate_relation(element)
        else:
            raise NotImplementedError(f'Unsupported element type {type!r}')

        if element['visible']:
            _validate_visible(element)
        else:
            _validate_hidden(element)

    return elements


@cython.cfunc
def _validate_node(element: ElementInit):
    element['members'] = None
    element['members_roles'] = None


@cython.cfunc
def _validate_way(element: ElementInit):
    element['point'] = None
    element['members_roles'] = None

    if not element['visible']:
        return

    members = element['members']

    if not members:
        raise ValueError('Ways must have at least one member')
    if len(members) > ELEMENT_WAY_MEMBERS_LIMIT:
        raise ValueError(f'Ways cannot have more than {ELEMENT_WAY_MEMBERS_LIMIT} members')
    if np.any(np.array(members, np.uint64) > TYPED_ELEMENT_ID_NODE_MAX):
        raise ValueError('Ways cannot have non-node members')


@cython.cfunc
def _validate_relation(element: ElementInit):
    element['point'] = None

    if not element['visible']:
        return

    members = element['members']
    members_roles = element['members_roles']

    # TODO: 0.7
    # if not members:
    #     raise ValueError('Relations must have at least one member')
    if members is None:
        members = element['members'] = []
    if members_roles is None:
        members_roles = element['members_roles'] = []
    if len(members) > ELEMENT_RELATION_MEMBERS_LIMIT:
        raise ValueError(f'Relations cannot have more than {ELEMENT_RELATION_MEMBERS_LIMIT} members')

    assert len(members) == len(members_roles), 'members and members_roles must have the same size'


@cython.cfunc
def _validate_visible(element: ElementInit):
    if element['tags'] is None:
        element['tags'] = {}


@cython.cfunc
def _validate_hidden(element: ElementInit):
    if element['version'] == 1:
        raise ValueError('Element cannot be hidden on creation')

    element['tags'] = None
    element['point'] = None
    element['members'] = None
    element['members_roles'] = None
