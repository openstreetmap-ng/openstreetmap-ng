import cython
from typing import Any, NamedTuple

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


class PaginationResult(NamedTuple):
    """Result of pagination calculation containing cursor information."""
    limit: int
    offset: int
    cursors: list[Any] | None = None


def standard_pagination_range(
    page: cython.int,
    *,
    page_size: cython.ulonglong,
    num_items: cython.ulonglong,
    reverse: bool = True,
) -> tuple[int, int]:
    """
    Get the range of items for the given page.

    Two pagination modes:
    - reverse=True (default): Optimized for accessing the end of result sets.
      Last page has offset 0, page 1 has the highest offset.
      Efficient when users typically view the last page (newest comments, recent activity).

    - reverse=False: Optimized for accessing the start of result sets.
      Page 1 has offset 0, last page has the highest offset.
      Efficient when users typically start from page 1 (alphabetical lists, search results).

    Returns a tuple of (limit, offset).
    """
    num_pages: cython.int = int(ceil(num_items / page_size))  # noqa: RUF046
    if not (1 <= page <= num_pages):
        return 0, 0

    offset: cython.ulonglong = (
        (num_pages - page) * page_size if reverse else (page - 1) * page_size
    )
    limit: cython.ulonglong = min(page_size, num_items - offset)
    return limit, offset


def generate_pagination_cursors(
    items: list[dict[str, Any]], 
    *, 
    cursor_field: str,
    page_size: int,
    total_available: int | None = None
) -> list[Any]:
    """
    Generate cursor values for cursor-based pagination from a list of items.
    
    Args:
        items: List of database items with cursor field
        cursor_field: Field name to use for cursor values (e.g., 'id', 'updated_at')
        page_size: Number of items per page
        total_available: Total number of items available (for optimization)
    
    Returns:
        List of cursor values representing page boundaries
    """
    if not items:
        return []
    
    cursors = []
    
    # Generate cursors based on the items
    for i in range(0, len(items), page_size):
        if i < len(items):
            cursors.append(items[i][cursor_field])
    
    return cursors


def cursor_pagination_params(
    cursor: Any | None,
    *,
    direction: str = 'after',
    page_size: int = 20,
    cursor_field: str = 'id'
) -> dict[str, Any]:
    """
    Generate parameters for cursor-based database queries.
    
    Args:
        cursor: The cursor value to paginate from (None for first page)
        direction: 'after' for next pages, 'before' for previous pages  
        page_size: Number of items per page
        cursor_field: Database field used for cursor
    
    Returns:
        Dictionary with query parameters
    """
    params = {
        'limit': page_size,
        cursor_field: cursor,
        'direction': direction
    }
    
    return {k: v for k, v in params.items() if v is not None}
