import cython

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


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
