from collections.abc import Sequence

import cython

from app.lib.feature_icon import feature_icon
from app.lib.feature_name import feature_name
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element_list_entry import ChangesetElementEntry, ElementMemberEntry
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.queries.element_query import ElementQuery


async def format_changeset_elements_list(
    elements: Sequence[Element],
) -> dict[ElementType, Sequence[ChangesetElementEntry]]:
    """
    Format elements for displaying on the website (icons, strikethrough, sort).

    Returns a mapping of element types to sequences of ElementStyle.
    """
    # element.version > 1 is mostly redundant
    # but ensures backward-compatible compliance for PositiveInt
    prev_refs: tuple[VersionedElementRef, ...] = tuple(
        VersionedElementRef(element.type, element.id, element.version - 1)
        for element in elements
        if not element.visible and element.version > 1
    )

    if prev_refs:
        prev_elements = await ElementQuery.get_by_versioned_refs(prev_refs, limit=len(prev_refs))
        prev_type_id_map = {(element.type, element.id): element for element in prev_elements}
    else:
        prev_type_id_map = {}

    result: dict[ElementType, list[ChangesetElementEntry]] = {'node': [], 'way': [], 'relation': []}

    for element in elements:
        prev = prev_type_id_map.get((element.type, element.id))
        tags = prev.tags if (prev is not None) else element.tags

        if tags:
            name = feature_name(tags)
            resolved = feature_icon(element.type, tags)
        else:
            name = None
            resolved = None

        if resolved is not None:
            icon = resolved[0]
            icon_title = resolved[1]
        else:
            icon = None
            icon_title = None

        result[element.type].append(
            ChangesetElementEntry(
                type=element.type,
                id=element.id,
                name=name,
                version=element.version,
                visible=element.visible,
                icon=icon,
                icon_title=icon_title,
            )
        )

    for v in result.values():
        v.sort(key=_sort_key)

    return result


def format_element_parents_list(ref: ElementRef, parents: Sequence[Element]) -> Sequence[ElementMemberEntry]:
    result: list[ElementMemberEntry] = []

    for element in parents:
        tags = element.tags

        if tags:
            name = feature_name(tags)
            resolved = feature_icon(element.type, tags)
        else:
            name = None
            resolved = None

        if resolved is not None:
            icon = resolved[0]
            icon_title = resolved[1]
        else:
            icon = None
            icon_title = None

        if element.type == 'relation':
            role = ', '.join(
                sorted(
                    {
                        member_ref.role
                        for member_ref in element.members
                        if member_ref.role and member_ref.id == ref.id and member_ref.type == ref.type
                    }
                )
            )
        else:
            role = ''

        result.append(
            ElementMemberEntry(
                type=element.type,
                id=element.id,
                name=name,
                icon=icon,
                icon_title=icon_title,
                role=role,
            )
        )

    return result


def format_element_members_list(
    members: Sequence[ElementMember],
    members_elements: Sequence[Element],
) -> Sequence[ElementMemberEntry]:
    type_id_map: dict[tuple[ElementType, int], Element] = {
        (member.type, member.id): member  #
        for member in members_elements
    }
    result: list[ElementMemberEntry] = []

    for member in members:
        member_type = member.type
        member_id = member.id
        element = type_id_map.get((member_type, member_id))
        if element is None:
            continue

        tags = element.tags

        if tags:
            name = feature_name(tags)
            resolved = feature_icon(member_type, tags)
        else:
            name = None
            resolved = None

        if resolved is not None:
            icon = resolved[0]
            icon_title = resolved[1]
        else:
            icon = None
            icon_title = None

        result.append(
            ElementMemberEntry(
                type=member_type,
                id=member_id,
                name=name,
                icon=icon,
                icon_title=icon_title,
                role=member.role,
            )
        )

    return result


@cython.cfunc
def _sort_key(element: Element) -> tuple:
    return (not element.visible, element.id, element.version)
