import cython

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


# TODO: support &before= for consistency
def standard_pagination_range(
    page: cython.int,
    *,
    page_size: cython.int,
    num_items: cython.longlong,
) -> tuple[int, int]:
    """
    Get the range of items for the given page.

    The last page returns an offset of 0.

    Returns a tuple of (limit, offset).
    """
    num_pages: cython.int = int(ceil(num_items / page_size))
    if page < 1 or page > num_pages:
        return 0, 0
    stmt_offset: cython.longlong = (num_pages - page) * page_size
    stmt_limit = page_size
    return stmt_limit, stmt_offset
