import pytest

from app.config import STANDARD_PAGINATION_DISTANCE
from app.lib.standard_pagination import (
    _cursor_codec,
    _plan,
    _update_discovery,
)
from app.models.proto.shared_pb2 import StandardPaginationState


@pytest.mark.parametrize(
    (
        'requested_page',
        'expected_order_dir',
        'expected_offset',
        'expected_anchor_op',
        'expected_anchor_id',
    ),
    [
        # Page 1 is always a special-case.
        (1, 'desc', 0, None, None),
        # Forward (page increases): use keyset anchor + small offset.
        (6, 'desc', 0, '<', 41),
        (7, 'desc', 10, '<', 41),
        # Backward (page decreases): use keyset anchor + small offset, but query in reverse order.
        (4, 'asc', 0, '>', 50),
        (3, 'asc', 10, '>', 50),
    ],
)
def test_sp_plan_prefers_cursor_anchors_for_nearby_pages(
    requested_page,
    expected_order_dir,
    expected_offset,
    expected_anchor_op,
    expected_anchor_id,
):
    # Arrange
    state = StandardPaginationState(
        current_page=5,
        page_size=10,
        snapshot_max_id=100,
        # Boundaries of the current page in primary order (desc).
        page_first_id=50,
        page_last_id=41,
        max_known_page=7,
    )
    state.u64.page_first = 50
    state.u64.page_last = 41

    # Act
    plan = _plan(
        state,
        requested_page=requested_page,
        cursor_codec=_cursor_codec('id'),
        order_dir='desc',
        distance=STANDARD_PAGINATION_DISTANCE,
    )

    # Assert
    assert plan.order_dir == expected_order_dir
    assert plan.offset == expected_offset
    assert plan.anchor_op == expected_anchor_op
    if expected_anchor_id is None:
        assert plan.anchor is None
    else:
        assert plan.anchor is not None
        assert plan.anchor[1] == expected_anchor_id


def test_sp_plan_uses_reverse_shortcut_when_last_page_known():
    # Arrange
    state = StandardPaginationState(
        current_page=1,
        page_size=15,
        snapshot_max_id=100,
        max_known_page=7,
        num_pages=7,
        num_items=100,
    )

    # Act
    plan = _plan(
        state,
        requested_page=7,
        cursor_codec=_cursor_codec('id'),
        order_dir='desc',
        distance=STANDARD_PAGINATION_DISTANCE,
    )

    # Assert
    assert plan.order_dir == 'asc'
    assert plan.offset == 0
    assert plan.limit == 10


def test_sp_plan_falls_back_to_closest_end_when_last_page_known():
    # Arrange
    state = StandardPaginationState(
        current_page=1,
        page_size=15,
        snapshot_max_id=100,
        max_known_page=7,
        num_pages=7,
        num_items=100,
    )

    # Act
    plan = _plan(
        state,
        requested_page=6,
        cursor_codec=_cursor_codec('id'),
        order_dir='desc',
        distance=STANDARD_PAGINATION_DISTANCE,
    )

    # Assert
    assert plan.order_dir == 'asc'
    assert plan.offset == 10
    assert plan.limit == 15


def test_sp_update_discovery_sets_exact_end_when_no_more_items():
    # Arrange
    state = StandardPaginationState(current_page=1, page_size=10, max_known_page=1)

    # Act
    _update_discovery(state, current_page_items=7, remaining_items_limited=0)

    # Assert
    assert state.num_pages == 1
    assert state.num_items == 7
    assert state.max_known_page == 1


def test_sp_update_discovery_discovers_last_page_within_lookahead_window():
    # Arrange
    state = StandardPaginationState(current_page=3, page_size=10, max_known_page=3)

    # Act
    _update_discovery(state, current_page_items=10, remaining_items_limited=11)

    # Assert
    assert state.num_pages == 5
    assert state.num_items == 41
    assert state.max_known_page == 5


def test_sp_update_discovery_extends_max_known_page_when_end_not_within_lookahead():
    # Arrange
    state = StandardPaginationState(current_page=4, page_size=10, max_known_page=4)

    # Act
    _update_discovery(state, current_page_items=10, remaining_items_limited=21)

    # Assert
    assert not state.HasField('num_pages')
    assert state.max_known_page == 4 + STANDARD_PAGINATION_DISTANCE


def test_sp_update_discovery_does_not_shrink_max_known_page():
    # Arrange
    state = StandardPaginationState(current_page=1, page_size=10, max_known_page=8)

    # Act
    _update_discovery(
        state,
        current_page_items=10,
        remaining_items_limited=10_000,
        distance=STANDARD_PAGINATION_DISTANCE,
    )

    # Assert
    assert not state.HasField('num_pages')
    assert state.max_known_page == 8
