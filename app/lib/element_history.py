from app.config import ELEMENT_HISTORY_PAGE_SIZE

ELEMENT_HISTORY_PAGE_SIZE_MAX = 100


def history_page_size(page_size: int) -> int:
    return (
        ELEMENT_HISTORY_PAGE_SIZE
        if page_size <= 0
        else min(page_size, ELEMENT_HISTORY_PAGE_SIZE_MAX)
    )
