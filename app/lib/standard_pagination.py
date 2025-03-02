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
) -> tuple[int, int]:
    """
    Get the range of items for the given page.

    The last page returns an offset of 0.

    Returns a tuple of (limit, offset).
    """
    num_pages: cython.int = int(ceil(num_items / page_size))
    if 1 <= page <= num_pages:
        return page_size, (num_pages - page) * page_size
    return 0, 0
