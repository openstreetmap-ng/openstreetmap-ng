import logging
import pathlib
import tomllib
from collections.abc import Sequence

import cython

from app.config import CONFIG_DIR
from app.lib.feature_name import feature_name
from app.models.db.element import Element
from app.models.element_list_entry import ChangesetElementEntry, ElementMemberEntry
from app.models.element_member_ref import ElementMemberRef
from app.models.element_ref import ElementRef, VersionedElementRef
from app.models.element_type import ElementType
from app.repositories.element_repository import ElementRepository


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
        prev_elements = await ElementRepository.get_many_by_versioned_refs(prev_refs, limit=len(prev_refs))
        prev_ref_map = {element.element_ref: element for element in prev_elements}
    else:
        prev_ref_map = {}

    result: dict[ElementType, list[ChangesetElementEntry]] = {'node': [], 'way': [], 'relation': []}

    for element in elements:
        prev = prev_ref_map.get(element.element_ref)
        tags = prev.tags if (prev is not None) else element.tags
        resolved = _resolve_icon(element.type, tags)

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
                name=feature_name(tags) if tags else None,
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
        resolved = _resolve_icon(element.type, tags)

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
                        if member_ref.role and member_ref.type == ref.type and member_ref.id == ref.id
                    }
                )
            )
        else:
            role = ''

        result.append(
            ElementMemberEntry(
                type=element.type,
                id=element.id,
                name=feature_name(tags) if tags else None,
                icon=icon,
                icon_title=icon_title,
                role=role,
            )
        )

    return result


def format_element_members_list(
    member_refs: Sequence[ElementMemberRef],
    members: Sequence[Element],
) -> Sequence[ElementMemberEntry]:
    ref_map: dict[ElementRef, Element] = {member.element_ref: member for member in members}
    result: list[ElementMemberEntry] = []

    for ref in member_refs:
        element = ref_map.get(ref.element_ref)
        if element is None:
            continue

        tags = element.tags
        resolved = _resolve_icon(element.type, tags)

        if resolved is not None:
            icon = resolved[0]
            icon_title = resolved[1]
        else:
            icon = None
            icon_title = None

        result.append(
            ElementMemberEntry(
                type=ref.type,
                id=ref.id,
                name=feature_name(tags) if tags else None,
                icon=icon,
                icon_title=icon_title,
                role=ref.role,
            )
        )

    return result


@cython.cfunc
def _resolve_icon(type: ElementType, tags: dict[str, str]):
    """
    Get the filename and title of the icon for an element.

    Returns None if no appropriate icon is found.

    >>> _resolve_icon(...)
    'aeroway_terminal.webp', 'aeroway=terminal'
    """

    # small optimization, most elements don't have any tags
    if not tags:
        return None

    matched_keys = _config_keys.intersection(tags)

    # 1. check value-specific configuration
    for key in matched_keys:
        key_value = tags[key]
        key_config: dict[str, str | dict[str, str]] = _config[key]
        type_config: dict[str, str] | None = key_config.get(type)

        # prefer type-specific configuration
        if (type_config is not None) and (icon := type_config.get(key_value)) is not None:
            return icon, f'{key}={key_value}'

        if (icon := key_config.get(key_value)) is not None and isinstance(icon, str):
            return icon, f'{key}={key_value}'

    # 2. check key-specific configuration (generic)
    for key in matched_keys:
        key_config: dict[str, str | dict[str, str]] = _config[key]
        type_config: dict[str, str] | None = key_config.get(type)

        # prefer type-specific configuration
        if (type_config is not None) and (icon := type_config.get('*')) is not None:
            return icon, key

        if (icon := key_config.get('*')) is not None:
            return icon, key

    return None


@cython.cfunc
def _sort_key(element: Element) -> tuple:
    return (not element.visible, element.id, element.version)


@cython.cfunc
def _get_config() -> dict[str, dict[str, str | dict[str, str]]]:
    """
    Get the feature icon configuration.

    Generic icons are stored under the value '*'.
    """
    return tomllib.loads(pathlib.Path(CONFIG_DIR / 'feature_icons.toml').read_text())


# _config[tag_key][tag_value] = icon
# _config[tag_key][type][tag_value] = icon
_config = _get_config()
_config_keys = frozenset(_config)
_num_icons = 0

# raise an exception if any of the icons are missing
for key_config in _config.values():
    for icon_or_type_config in key_config.values():
        icon_or_type_config: str | dict

        icons = (icon_or_type_config,) if isinstance(icon_or_type_config, str) else icon_or_type_config.values()
        _num_icons += len(icons)

        for icon in icons:
            path = pathlib.Path('app/static/img/element/' + icon)
            if not path.is_file():
                raise FileNotFoundError(path)

logging.info('Loaded %d feature icons', _num_icons)
