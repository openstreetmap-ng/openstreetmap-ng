from collections.abc import Iterable
from typing import TypeVar

import cython

from app.lib.discardable_tags import has_non_discardable_tags
from app.models.db.element import ElementInit
from app.models.element import TypedElementId

_T = TypeVar('_T', bound=ElementInit)


class ElementsFilter:
    @staticmethod
    def filter_nodes_interesting(
        nodes: Iterable[_T],
        member_nodes: set[TypedElementId],
        *,
        detailed: cython.bint,
    ):
        """Return only interesting nodes."""
        return [
            node
            for node in nodes
            if _check_node_interesting(node, member_nodes, detailed=detailed)
        ]

    @staticmethod
    def filter_tags_interesting(elements: list[_T]):
        """Return only elements with interesting tags."""
        return [
            element  #
            for element in elements
            if has_non_discardable_tags(element['tags'])
        ]


@cython.cfunc
def _check_node_interesting(
    node: ElementInit,
    member_nodes: set[TypedElementId],
    *,
    detailed: cython.bint,
):
    if node['point'] is None:
        return False

    is_member: cython.bint = node['typed_id'] in member_nodes
    return (
        (not is_member or has_non_discardable_tags(node['tags']))
        if detailed
        else (not is_member and has_non_discardable_tags(node['tags']))
    )
