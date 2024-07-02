from collections.abc import Sequence
from dataclasses import dataclass

import cython

from app.lib.feature_icon import feature_icon
from app.lib.feature_name import feature_name
from app.models.db.element import Element
from app.models.db.element_member import ElementMember
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
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
    async def changeset_elements(elements: Sequence[Element]) -> dict[ElementType, list[ChangesetListEntry]]:
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

        result: dict[ElementType, list[ChangesetListEntry]] = {'node': [], 'way': [], 'relation': []}

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
                ChangesetListEntry(
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

    @staticmethod
    def element_parents(ref: ElementRef, parents: Sequence[Element]) -> list[MemberListEntry]:
        result: list[MemberListEntry] = []

        for element in parents:
            type = element.type
            tags = element.tags
            members = element.members

            if tags:
                name = feature_name(tags)
                resolved = feature_icon(type, tags)
            else:
                name = None
                resolved = None

            if resolved is not None:
                icon = resolved[0]
                icon_title = resolved[1]
            else:
                icon = None
                icon_title = None

            if type == 'relation':
                if members is None:
                    raise ValueError('Element is missing members')

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

            result.append(
                MemberListEntry(
                    type=type,
                    id=element.id,
                    name=name,
                    icon=icon,
                    icon_title=icon_title,
                    role=role,
                )
            )

        return result

    @staticmethod
    def element_members(
        members: Sequence[ElementMember],
        members_elements: Sequence[Element],
    ) -> list[MemberListEntry]:
        type_id_map: dict[tuple[ElementType, int], Element] = {
            (member.type, member.id): member  #
            for member in members_elements
        }
        result: list[MemberListEntry] = []

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
                MemberListEntry(
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
