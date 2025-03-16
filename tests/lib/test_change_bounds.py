from shapely import MultiPolygon, Point, box

from app.lib.changeset_bounds import extend_changeset_bounds
from app.limits import CHANGESET_BBOX_LIMIT, CHANGESET_NEW_BBOX_MIN_DISTANCE, CHANGESET_NEW_BBOX_MIN_RATIO


def test_multiple_sequential_extensions():
    bounds = MultiPolygon()

    # Empty bounds and no points
    result = extend_changeset_bounds(bounds, [])
    assert len(result.geoms) == 0, 'Empty inputs must produce empty result'

    # First extension
    point1 = Point(0, 0)
    bounds = extend_changeset_bounds(bounds, [point1])
    assert len(bounds.geoms) == 1, 'Initial point must create a single boundary'

    # Second extension with close point
    close_point = Point(CHANGESET_NEW_BBOX_MIN_DISTANCE * 0.5, 0)
    bounds = extend_changeset_bounds(bounds, [close_point])
    assert len(bounds.geoms) == 1, 'Close point must merge with existing boundary'

    # Third extension with distant point
    far_point = Point(CHANGESET_NEW_BBOX_MIN_DISTANCE * 3, 0)
    bounds = extend_changeset_bounds(bounds, [far_point])
    assert len(bounds.geoms) == 2, 'Distant point must create a new boundary'


def test_points_at_threshold_merge():
    x = CHANGESET_NEW_BBOX_MIN_DISTANCE
    points = [Point(0, 0), Point(x, x)]

    result = extend_changeset_bounds(MultiPolygon(), points)

    assert len(result.geoms) == 1, 'Points at threshold distance must merge into a single boundary'
    assert result.geoms[0].bounds == (0, 0, x, x), 'Boundary must contain both points'


def test_points_beyond_threshold_separate():
    x = CHANGESET_NEW_BBOX_MIN_DISTANCE * 1.01
    points = [Point(0, 0), Point(x, x)]

    result = extend_changeset_bounds(MultiPolygon(), points)

    # Verify both points created separate boundaries
    assert len(result.geoms) == 2, 'Points beyond threshold distance must create separate boundaries'
    point_coords = {(0, 0), (x, x)}
    result_coords = {(p.bounds[0], p.bounds[1]) for p in result.geoms}
    assert point_coords == result_coords, 'Each point must create its own boundary at the correct coordinates'


def test_points_within_ratio_of_bounds_merge():
    # Point just within ratio threshold
    x = CHANGESET_NEW_BBOX_MIN_RATIO * 0.9
    points = [Point(x, x)]
    existing_bounds = MultiPolygon([box(-1, -1, 0, 0)])

    result = extend_changeset_bounds(existing_bounds, points)

    assert len(result.geoms) == 1, 'Point within ratio of existing boundary must merge with it'
    assert any(p.bounds[2] >= x and p.bounds[3] >= x for p in result.geoms), (
        'Boundary must expand to include the new point'
    )


def test_points_beyond_ratio_of_bounds_separate():
    # Point just beyond ratio threshold
    x = CHANGESET_NEW_BBOX_MIN_RATIO * 1.1
    points = [Point(x, x)]
    existing_bounds = MultiPolygon([box(-1, -1, 0, 0)])

    result = extend_changeset_bounds(existing_bounds, points)

    assert len(result.geoms) == 2, 'Point beyond ratio of existing boundary must create a new boundary'
    assert any(p.bounds == (-1, -1, 0, 0) for p in result.geoms), 'Original boundary must be preserved'
    assert any(p.bounds[0] == x and p.bounds[1] == x for p in result.geoms), (
        'New boundary must be created at point location'
    )


def test_early_merge_behavior():
    x = -CHANGESET_NEW_BBOX_MIN_DISTANCE
    y = CHANGESET_NEW_BBOX_MIN_DISTANCE * 0.9
    z = CHANGESET_NEW_BBOX_MIN_DISTANCE * 1.5

    existing_bounds = MultiPolygon([box(x, x, 0, 0)])
    points = [Point(y, y), Point(z, z)]

    result = extend_changeset_bounds(existing_bounds, points)

    assert len(result.geoms) == 1, 'Close points must merge into a single boundary'
    bounds = result.geoms[0].bounds
    assert bounds[0] <= x, "Boundary must include original boundary's min X"
    assert bounds[1] <= x, "Boundary must include original boundary's min Y"
    assert bounds[2] >= z, "Boundary must extend to include the furthest point's X"
    assert bounds[3] >= z, "Boundary must extend to include the furthest point's Y"


def test_bbox_limit_new_bounds():
    # Create more points than the limit
    points = [Point(i * CHANGESET_NEW_BBOX_MIN_DISTANCE * 2, 0) for i in range(CHANGESET_BBOX_LIMIT * 2)]

    result = extend_changeset_bounds(MultiPolygon(), points)

    assert len(result.geoms) == CHANGESET_BBOX_LIMIT, 'Number of boundaries must not exceed CHANGESET_BBOX_LIMIT'


def test_bbox_limit_merge():
    # Create boundaries just under the limit
    existing_bounds = MultiPolygon([box(i * 10, 0, i * 10 + 1, 1) for i in range(CHANGESET_BBOX_LIMIT - 1)])

    # Add enough points to exceed the limit if all created separate boundaries
    points = [Point((CHANGESET_BBOX_LIMIT + i) * 10, 0) for i in range(3)]

    result = extend_changeset_bounds(existing_bounds, points)

    assert len(result.geoms) == CHANGESET_BBOX_LIMIT, (
        'When adding new points, total boundaries must not exceed CHANGESET_BBOX_LIMIT'
    )
