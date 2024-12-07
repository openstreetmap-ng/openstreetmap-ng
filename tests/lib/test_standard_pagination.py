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
def test_standard_pagination_range(page: int, expected: tuple[int, int]):
    page_size = 10
    num_items = 23
    assert standard_pagination_range(page, page_size=page_size, num_items=num_items) == expected
