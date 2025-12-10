import cython

from app.lib.feature_name import features_names
from app.models.db.element import Element
from app.models.element import ElementType, TypedElementId
from app.models.proto.shared_pb2 import (
    PartialChangesetParams,
    PartialElementParams,
)
from app.queries.element_query import ElementQuery
from speedup.element_type import split_typed_element_id


class FormatElementList:
    @staticmethod
    async def changeset_elements(
        elements: list[Element],
    ) -> dict[ElementType, list[PartialChangesetParams.Element]]:
        """Format elements for displaying on the website (icons, strikethrough, sort)."""
        if not elements:
            return {'node': [], 'way': [], 'relation': []}

        # element.version > 1 is mostly redundant
        # but ensures backward-compatible compliance for PositiveInt
        prev_refs: list[tuple[TypedElementId, int]] = [
            (element['typed_id'], element['version'] - 1)
            for element in elements
            if not element['visible'] and element['version'] > 1
        ]
        prev_elements = await ElementQuery.find_by_versioned_refs(
            prev_refs, limit=len(prev_refs)
        )
        prev_type_id_map: dict[TypedElementId, Element]
        prev_type_id_map = {element['typed_id']: element for element in prev_elements}
        tagged_elements = (
            [
                prev_type_id_map.get(element['typed_id'], element)
                if not element['visible'] and element['version'] > 1
                else element
                for element in elements
            ]
            if prev_type_id_map
            else elements
        )

        result = _encode_elements(
            elements, features_names(tagged_elements), tagged_elements
        )
        for v in result.values():
            v.sort(key=_sort_key)
        return result

    @staticmethod
    def element_parents(
        ref: TypedElementId,
        parents: list[Element],
    ) -> list[PartialElementParams.Entry]:
        return _encode_parents(ref, parents, features_names(parents)) if parents else []

    @staticmethod
    def element_members(
        members: list[TypedElementId] | None,
        members_roles: list[str] | None,
        members_elements: list[Element],
    ) -> list[PartialElementParams.Entry]:
        if not members:
            return []

        type_id_map: dict[TypedElementId, tuple[str | None, dict[str, str] | None]]
        type_id_map = {
            element['typed_id']: (name, element['tags'])
            for element, name in zip(
                members_elements,
                features_names(members_elements),
                strict=True,
            )
        }
        return _encode_members(type_id_map, members, members_roles)


@cython.cfunc
def _encode_elements(
    elements: list[Element],
    names: list[str | None],
    tagged_elements: list[Element],
):
    result: dict[ElementType, list[PartialChangesetParams.Element]] = {
        'node': [],
        'way': [],
        'relation': [],
    }
    for element, name, tagged in zip(elements, names, tagged_elements, strict=True):
        type, id = split_typed_element_id(element['typed_id'])
        result[type].append(
            PartialChangesetParams.Element(
                id=id,
                version=element['version'],
                visible=element['visible'],
                name=name,
                tags=tagged['tags'],
            )
        )
    return result


@cython.cfunc
def _encode_parents(
    ref: TypedElementId,
    parents: list[Element],
    names: list[str | None],
):
    result: list[PartialElementParams.Entry] = []
    for parent, name in zip(parents, names, strict=True):
        type, id = split_typed_element_id(parent['typed_id'])
        role = (
            ', '.join(
                sorted({
                    role
                    for member, role in zip(
                        parent['members'] or (),
                        parent['members_roles'] or (),
                        strict=True,
                    )
                    if role and member == ref
                })
            )
            if type == 'relation'
            else None
        )
        result.append(
            PartialElementParams.Entry(
                type=type,
                id=id,
                role=role,
                name=name,
                tags=parent['tags'],
            )
        )
    return result


@cython.cfunc
def _encode_members(
    type_id_map: dict[TypedElementId, tuple[str | None, dict[str, str] | None]],
    members: list[TypedElementId],
    members_roles: list[str] | list[None] | None,
):
    if members_roles is None:
        members_roles = [None] * len(members)

    result: list[PartialElementParams.Entry] = []
    for member, role in zip(members, members_roles, strict=True):
        data = type_id_map.get(member)
        name, tags = data or (None, None)
        type, id = split_typed_element_id(member)
        result.append(
            PartialElementParams.Entry(
                type=type,
                id=id,
                role=role,
                name=name,
                tags=tags,
            )
        )
    return result


@cython.cfunc
def _sort_key(element: PartialChangesetParams.Element) -> tuple:
    return not element.visible, element.id, element.version
