from collections.abc import Iterable, Set

import cython

from app.models.db.element import Element
from app.models.element import ElementId


class ElementsFilter:
    @staticmethod
    def filter_nodes_interesting(
        nodes: Iterable[Element],
        member_nodes_ids: Set[ElementId],
        *,
        detailed: cython.char,
    ) -> tuple[Element, ...]:
        """
        Return only interesting nodes.
        """
        return tuple(
            node
            for node in nodes  #
            if _check_node_interesting(node, member_nodes_ids, detailed=detailed)
        )

    @staticmethod
    def filter_tags_interesting(elements: Iterable[Element]) -> tuple[Element, ...]:
        """
        Return only elements with interesting tags.
        """
        return tuple(
            element
            for element in elements  #
            if _check_tags_interesting(element.tags)
        )


@cython.cfunc
def _check_node_interesting(
    node: Element,
    member_nodes_ids: Set[ElementId],
    *,
    detailed: cython.char,
) -> cython.char:
    if node.point is None:
        return False
    is_member: cython.char = node.id in member_nodes_ids
    return (
        (not is_member or _check_tags_interesting(node.tags))
        if detailed
        else (not is_member and _check_tags_interesting(node.tags))
    )


@cython.cfunc
def _check_tags_interesting(tags: dict[str, str]) -> cython.char:
    # TODO: consider discardable tags
    # https://github.com/openstreetmap-ng/openstreetmap-ng/issues/110
    return bool(tags)
