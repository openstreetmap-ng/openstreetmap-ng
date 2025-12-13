from collections.abc import Mapping

import cython
from starlette.responses import Response

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


@cython.cfunc
def _sp_num_pages(*, num_items: int, page_size: int) -> int:
    """
    Compute total pages from num_items/page_size.
    StandardPagination always reports at least 1 page (even for empty lists).
    """
    return max(1, int(ceil(num_items / page_size)))  # noqa: RUF046


def sp_resolve_page(*, page: int, num_items: int, page_size: int) -> int:
    """Resolve `page=0` into the last page; otherwise return page unchanged."""
    return page or _sp_num_pages(num_items=num_items, page_size=page_size)


def sp_apply_headers(
    response: Response,
    *,
    num_items: int,
    page_size: int,
    extra: Mapping[str, str] | None = None,
) -> None:
    """
    Apply StandardPagination headers to an existing response object.

    This avoids allocating a headers dict at hot call sites.
    """
    response.headers['X-SP-NumItems'] = str(num_items)
    response.headers['X-SP-NumPages'] = str(
        _sp_num_pages(num_items=num_items, page_size=page_size)
    )
    if extra:
        response.headers.update(extra)


def standard_pagination_range(
    page: cython.size_t,
    *,
    page_size: cython.size_t,
    num_items: cython.size_t,
    start_from_end: bool = True,
) -> tuple[int, int]:
    """
    Get the range of items for the given page.

    Two pagination modes:
    - start_from_end=True (default): Optimized for accessing the end of result sets.
      Last page has offset 0, page 1 has the highest offset.
      Efficient when users typically view the last page (newest comments, recent activity).

    - start_from_end=False: Optimized for accessing the start of result sets.
      Page 1 has offset 0, last page has the highest offset.
      Efficient when users typically start from page 1 (alphabetical lists, search results).

    Returns a tuple of (limit, offset).
    """
    num_pages: cython.size_t = int(ceil(num_items / page_size))  # noqa: RUF046
    if not (1 <= page <= num_pages):
        return 0, 0

    offset: cython.size_t = (
        (num_pages - page) * page_size if start_from_end else (page - 1) * page_size
    )
    limit: cython.size_t = min(page_size, num_items - offset)
    return limit, offset
