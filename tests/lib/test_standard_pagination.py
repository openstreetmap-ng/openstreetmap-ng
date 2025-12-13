import pytest

from app.lib.standard_pagination import standard_pagination_range


@pytest.mark.parametrize(
    ('page', 'expected'),
    [
        (0, (0, 0)),
        (1, (3, 20)),
        (2, (10, 10)),
        (3, (10, 0)),
        (4, (0, 0)),
    ],
)
def test_standard_pagination_range_reverse(page, expected):
    page_size = 10
    num_items = 23
    assert (
        standard_pagination_range(
            page,
            page_size=page_size,
            num_items=num_items,
            start_from_end=True,
        )
        == expected
    )


@pytest.mark.parametrize(
    ('page', 'expected'),
    [
        (0, (0, 0)),
        (1, (10, 0)),
        (2, (10, 10)),
        (3, (3, 20)),
        (4, (0, 0)),
    ],
)
def test_standard_pagination_range_forward(page, expected):
    page_size = 10
    num_items = 23
    assert (
        standard_pagination_range(
            page,
            page_size=page_size,
            num_items=num_items,
            start_from_end=False,
        )
        == expected
    )
