import pytest

from app.lib.standard_pagination import standard_pagination_range, generate_pagination_cursors, cursor_pagination_params


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
            reverse=True,
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
            reverse=False,
        )
        == expected
    )


def test_generate_pagination_cursors_empty():
    """Test cursor generation with empty items list."""
    cursors = generate_pagination_cursors([], cursor_field='id', page_size=10)
    assert cursors == []


def test_generate_pagination_cursors_single_page():
    """Test cursor generation with items fitting in one page."""
    items = [{'id': 1}, {'id': 2}, {'id': 3}]
    cursors = generate_pagination_cursors(items, cursor_field='id', page_size=10)
    assert cursors == [1]


def test_generate_pagination_cursors_multiple_pages():
    """Test cursor generation with items spanning multiple pages."""
    items = [
        {'id': 10}, {'id': 9}, {'id': 8}, {'id': 7}, {'id': 6},
        {'id': 5}, {'id': 4}, {'id': 3}, {'id': 2}, {'id': 1}
    ]
    cursors = generate_pagination_cursors(items, cursor_field='id', page_size=3)
    # Should generate cursors at page boundaries: [10, 7, 4, 1]
    assert cursors == [10, 7, 4, 1]


def test_generate_pagination_cursors_with_timestamp():
    """Test cursor generation using timestamp field."""
    items = [
        {'id': 1, 'updated_at': '2023-01-01'},
        {'id': 2, 'updated_at': '2023-01-02'},
        {'id': 3, 'updated_at': '2023-01-03'},
        {'id': 4, 'updated_at': '2023-01-04'},
        {'id': 5, 'updated_at': '2023-01-05'},
    ]
    cursors = generate_pagination_cursors(items, cursor_field='updated_at', page_size=2)
    assert cursors == ['2023-01-01', '2023-01-03', '2023-01-05']


def test_cursor_pagination_params_default():
    """Test cursor pagination parameters with defaults."""
    params = cursor_pagination_params(123)
    expected = {
        'limit': 20,  # default page_size
        'id': 123,    # default cursor_field
        'direction': 'after'
    }
    assert params == expected


def test_cursor_pagination_params_custom():
    """Test cursor pagination parameters with custom values."""
    params = cursor_pagination_params(
        cursor='2023-01-01',
        direction='before',
        page_size=50,
        cursor_field='created_at'
    )
    expected = {
        'limit': 50,
        'created_at': '2023-01-01',
        'direction': 'before'
    }
    assert params == expected


def test_cursor_pagination_params_none_cursor():
    """Test cursor pagination parameters with None cursor (first page)."""
    params = cursor_pagination_params(None, page_size=15)
    expected = {
        'limit': 15,
        'direction': 'after'
    }
    assert params == expected
