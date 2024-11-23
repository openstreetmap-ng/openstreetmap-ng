import cython

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


def standard_pagination_range(
    page: cython.int,
    *,
    page_size: cython.int,
    num_items: cython.longlong,
) -> tuple[int, int]:
    """
    Get the range of items for the given page.

    Returns a tuple of (limit, offset).
    """
    num_pages: cython.int = ceil(num_items / page_size)
    if page < 1 or page > num_pages:
        return 0, 0

    last_page_num_comments: cython.int = num_items - ((num_pages - 1) * page_size)
    adjust_offset: cython.int = page_size - last_page_num_comments

    stmt_limit: cython.int = page_size
    stmt_offset: cython.longlong = (page - 1) * page_size - adjust_offset
    if stmt_offset < 0:
        stmt_limit += stmt_offset
        stmt_offset = 0

    return stmt_limit, stmt_offset
