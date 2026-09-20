from typing import TYPE_CHECKING, cast

import pytest
from shapely import Point

from app.lib.geo.null_island import null_island_node_ids

if TYPE_CHECKING:
    from app.models.db.element import ElementInit


@pytest.mark.parametrize(
    ('revisions', 'expected'),
    [
        ([], set()),
        ([(1, True, Point(0, 0))], {1}),
        ([(1, True, Point(-0.0, 0.0)), (2, True, Point(0, 0))], {1, 2}),
        ([(1, True, Point(0, 1)), (2, True, Point(1, 0))], set()),
        ([(1, True, Point(0.0000001, 0))], set()),
        ([(1, True, None)], set()),
        ([(1, False, Point(0, 0))], set()),
        ([(1, True, Point(0, 0)), (1, True, Point(0, 0))], {1}),
        ([(1, True, Point(0, 0)), (1, True, Point(1, 1))], set()),
        ([(1, True, Point(0, 0)), (1, False, None)], set()),
        ([(1, True, Point(1, 1)), (1, True, Point(0, 0))], {1}),
    ],
)
def test_null_island_node_ids(revisions, expected):
    elements = [
        cast('ElementInit', {'typed_id': tid, 'visible': visible, 'point': point})
        for tid, visible, point in revisions
    ]
    assert null_island_node_ids(iter(elements)) == expected
