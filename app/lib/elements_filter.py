from collections.abc import Iterable, Set

import cython

from app.models.db.element import Element
from app.models.element import TypedElementId


class ElementsFilter:
    @staticmethod
    def filter_nodes_interesting(
        nodes: Iterable[Element],
        member_nodes: Set[TypedElementId],
        *,
        detailed: cython.char,
    ) -> list[Element]:
        """Return only interesting nodes."""
        return [
            node
            for node in nodes  #
            if _check_node_interesting(node, member_nodes, detailed=detailed)
        ]

    @staticmethod
    def filter_tags_interesting(elements: Iterable[Element]) -> list[Element]:
        """Return only elements with interesting tags."""
        return [
            element
            for element in elements  #
            if _check_tags_interesting(element['tags'])  # type: ignore
        ]


@cython.cfunc
def _check_node_interesting(
    node: Element,
    member_nodes: Set[TypedElementId],
    *,
    detailed: cython.char,
) -> cython.char:
    if node['point'] is None:
        return False

    is_member: cython.char = node['typed_id'] in member_nodes
    return (
        (not is_member or _check_tags_interesting(node['tags']))  # type: ignore
        if detailed
        else (not is_member and _check_tags_interesting(node['tags']))  # type: ignore
    )


@cython.cfunc
def _check_tags_interesting(tags: dict[str, str]) -> cython.char:
    # TODO: consider discardable tags
    # https://github.com/openstreetmap-ng/openstreetmap-ng/issues/110
    return bool(tags)
