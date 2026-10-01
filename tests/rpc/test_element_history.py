from app.config import ELEMENT_HISTORY_PAGE_SIZE
from app.lib.element_history import ELEMENT_HISTORY_PAGE_SIZE_MAX, history_page_size


def test_history_page_size_uses_default_for_omitted_request_value():
    assert history_page_size(0) == ELEMENT_HISTORY_PAGE_SIZE


def test_history_page_size_uses_requested_value_within_bounds():
    assert history_page_size(25) == 25


def test_history_page_size_caps_large_request_values():
    assert history_page_size(ELEMENT_HISTORY_PAGE_SIZE_MAX + 1) == (
        ELEMENT_HISTORY_PAGE_SIZE_MAX
    )
