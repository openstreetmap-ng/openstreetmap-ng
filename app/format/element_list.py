from collections.abc import Collection, Iterable
from dataclasses import dataclass

import cython

from app.lib.feature_icon import FeatureIcon, features_icons
from app.lib.feature_name import features_names
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element import ElementId, ElementRef, ElementType, VersionedElementRef
from app.queries.element_query import ElementQuery


@dataclass(frozen=True, slots=True)
class _Base:
    type: ElementType
    id: int
    name: str | None
    icon: str | None
    icon_title: str | None


@dataclass(frozen=True, slots=True)
class ChangesetListEntry(_Base):
    version: int
    visible: bool


@dataclass(frozen=True, slots=True)
class MemberListEntry(_Base):
    role: str | None


class FormatElementList:
    @staticmethod
    async def changeset_elements(elements: Collection[Element]) -> dict[ElementType, list[ChangesetListEntry]]:
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
        prev_elements = await ElementQuery.get_by_versioned_refs(prev_refs, limit=len(prev_refs))
        prev_type_id_map: dict[tuple[ElementType, ElementId], Element]
        prev_type_id_map = {(element.type, element.id): element for element in prev_elements}

        names = features_names(
            prev if (prev := prev_type_id_map.get((element.type, element.id))) is not None else element
            for element in elements
        )
        icons = features_icons(elements)
        result: dict[ElementType, list[ChangesetListEntry]] = {'node': [], 'way': [], 'relation': []}
        for element, name, icon in zip(elements, names, icons, strict=True):
            result[element.type].append(_encode_element(element, name, icon))
        for v in result.values():
            v.sort(key=_sort_key)
        return result

    @staticmethod
    def element_parents(ref: ElementRef, parents: Collection[Element]) -> tuple[MemberListEntry, ...]:
        names = features_names(parents)
        icons = features_icons(parents)
        return tuple(
            _encode_parent(ref, element, name, icon) for element, name, icon in zip(parents, names, icons, strict=True)
        )

    @staticmethod
    def element_members(
        members: Iterable[ElementMember],
        members_elements: Collection[Element],
    ) -> tuple[MemberListEntry, ...]:
        names = features_names(members_elements)
        icons = features_icons(members_elements)
        type_id_map: dict[tuple[ElementType, ElementId], tuple[str | None, FeatureIcon | None]]
        type_id_map = {
            (element.type, element.id): (name, icon)  #
            for element, name, icon in zip(members_elements, names, icons, strict=True)
        }
        encoded = (_encode_member(type_id_map, member) for member in members)
        return tuple(entry for entry in encoded if entry is not None)


@cython.cfunc
def _encode_element(
    element: Element,
    name: str | None,
    feature_icon: FeatureIcon | None,
):
    if feature_icon is not None:
        icon = feature_icon.filename
        icon_title = feature_icon.title
    else:
        icon = None
        icon_title = None

    return ChangesetListEntry(
        type=element.type,
        id=element.id,
        name=name,
        version=element.version,
        visible=element.visible,
        icon=icon,
        icon_title=icon_title,
    )


@cython.cfunc
def _encode_parent(
    ref: ElementRef,
    element: Element,
    name: str | None,
    feature_icon: FeatureIcon | None,
):
    element_type = element.type
    element_id = element.id

    if feature_icon is not None:
        icon = feature_icon.filename
        icon_title = feature_icon.title
    else:
        icon = None
        icon_title = None

    if element_type == 'relation':
        members = element.members
        if members is None:
            raise AssertionError('Relation members must be set')
        role = ', '.join(
            sorted(
                {
                    member_ref.role
                    for member_ref in members
                    if member_ref.role and member_ref.id == ref.id and member_ref.type == ref.type
                }
            )
        )
    else:
        role = ''

    return MemberListEntry(
        type=element_type,
        id=element_id,
        name=name,
        icon=icon,
        icon_title=icon_title,
        role=role,
    )


@cython.cfunc
def _encode_member(
    type_id_map: dict[tuple[ElementType, ElementId], tuple[str | None, FeatureIcon | None]],
    member: ElementMember,
):
    member_type = member.type
    member_id = member.id
    data = type_id_map.get((member_type, member_id))
    if data is None:
        return None
    name, feature_icon = data

    if feature_icon is not None:
        icon = feature_icon.filename
        icon_title = feature_icon.title
    else:
        icon = None
        icon_title = None

    return MemberListEntry(
        type=member_type,
        id=member_id,
        name=name,
        icon=icon,
        icon_title=icon_title,
        role=member.role,
    )


@cython.cfunc
def _sort_key(element: ChangesetListEntry) -> tuple:
    return (not element.visible, element.id, element.version)
