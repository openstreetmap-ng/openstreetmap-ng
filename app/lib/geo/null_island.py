from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.db.element import ElementInit
    from app.models.element import TypedElementId


def null_island_node_ids(elements: Iterable[ElementInit]) -> set[TypedElementId]:
    """Return distinct nodes left at (0, 0) after all supplied revisions."""
    result: set[TypedElementId] = set()
    for element in elements:
        typed_id = element['typed_id']
        point = element['point']
        if element['visible'] and point is not None and point.x == point.y == 0:
            result.add(typed_id)
        else:
            result.discard(typed_id)
    return result
