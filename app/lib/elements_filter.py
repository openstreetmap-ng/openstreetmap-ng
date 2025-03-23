from typing import TypeVar

import cython

from app.models.db.element import ElementInit
from app.models.element import TypedElementId

_T = TypeVar('_T', bound=ElementInit)


class ElementsFilter:
    @staticmethod
    def filter_nodes_interesting(
        nodes: list[_T],
        member_nodes: set[TypedElementId],
        *,
        detailed: cython.bint,
    ) -> list[_T]:
        """Return only interesting nodes."""
        return [node for node in nodes if _check_node_interesting(node, member_nodes, detailed=detailed)]

    @staticmethod
    def filter_tags_interesting(elements: list[_T]) -> list[_T]:
        """Return only elements with interesting tags."""
        return [element for element in elements if (tags := element['tags']) and _check_tags_interesting(tags)]


@cython.cfunc
def _check_node_interesting(
    node: ElementInit,
    member_nodes: set[TypedElementId],
    *,
    detailed: cython.bint,
) -> cython.bint:
    if node['point'] is None:
        return False

    is_member: cython.bint = node['typed_id'] in member_nodes
    return (
        (not is_member or _check_tags_interesting(node['tags']))  # type: ignore
        if detailed
        else (not is_member and _check_tags_interesting(node['tags']))  # type: ignore
    )


@cython.cfunc
def _check_tags_interesting(tags: dict[str, str]) -> cython.bint:
    # TODO: consider discardable tags
    # https://github.com/openstreetmap-ng/openstreetmap-ng/issues/110
    return bool(tags)
