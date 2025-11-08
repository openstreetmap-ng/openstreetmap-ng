import pytest
from shapely import MultiPolygon, Point, box

from app.config import (
    CHANGESET_BBOX_LIMIT,
    CHANGESET_NEW_BBOX_MIN_DISTANCE,
    CHANGESET_NEW_BBOX_MIN_RATIO,
)
from app.lib.changeset_bounds import extend_changeset_bounds


def test_creates_single_bbox_for_first_point():
    # Arrange
    bounds = MultiPolygon()
    p = Point(0, 0)

    # Act
    result = extend_changeset_bounds(bounds, [p])

    # Assert
    assert len(result.geoms) == 1
    assert result.geoms[0].bounds == (0.0, 0.0, 0.0, 0.0)


def test_merges_close_point_into_existing_bbox():
    # Arrange
    start = extend_changeset_bounds(MultiPolygon(), [Point(0, 0)])
    close = Point(CHANGESET_NEW_BBOX_MIN_DISTANCE * 0.5, 0)

    # Act
    result = extend_changeset_bounds(start, [close])

    # Assert
    assert len(result.geoms) == 1


def test_creates_new_bbox_for_distant_point():
    # Arrange
    start = extend_changeset_bounds(MultiPolygon(), [Point(0, 0)])
    far = Point(CHANGESET_NEW_BBOX_MIN_DISTANCE * 3, 0)

    # Act
    result = extend_changeset_bounds(start, [far])

    # Assert
    assert len(result.geoms) == 2


def test_empty_points_raise():
    # Arrange
    bounds = MultiPolygon()

    # Act / Assert
    with pytest.raises(AssertionError):
        extend_changeset_bounds(bounds, [])


def test_threshold_mode_merges_points_at_distance_threshold():
    # Arrange
    t = CHANGESET_NEW_BBOX_MIN_DISTANCE
    points = [Point(0, 0), Point(t, t)]

    # Act
    result = extend_changeset_bounds(MultiPolygon(), points)

    # Assert
    assert len(result.geoms) == 1
    assert result.geoms[0].bounds == (0.0, 0.0, t, t)


def test_threshold_mode_separates_points_beyond_distance():
    # Arrange
    t = CHANGESET_NEW_BBOX_MIN_DISTANCE * 1.01
    points = [Point(0, 0), Point(t, t)]

    # Act
    result = extend_changeset_bounds(MultiPolygon(), points)

    # Assert
    assert len(result.geoms) == 2
    mins = {(0.0, 0.0), (t, t)}
    got = {(p.bounds[0], p.bounds[1]) for p in result.geoms}
    assert got == mins


def test_threshold_mode_uses_chebyshev_metric():
    # Arrange (sqrt(2)*0.9t > t, but Chebyshev=0.9t <= t)
    t = CHANGESET_NEW_BBOX_MIN_DISTANCE
    points = [Point(0, 0), Point(0.9 * t, 0.9 * t)]

    # Act
    result = extend_changeset_bounds(MultiPolygon(), points)

    # Assert
    assert len(result.geoms) == 1


def test_merge_within_ratio_of_existing_bbox():
    # Arrange
    x = CHANGESET_NEW_BBOX_MIN_RATIO * 0.9
    existing_bounds = MultiPolygon([box(-1, -1, 0, 0)])
    p = Point(x, x)

    # Act
    result = extend_changeset_bounds(existing_bounds, [p])

    # Assert
    assert len(result.geoms) == 1
    assert any(b.bounds[2] >= x and b.bounds[3] >= x for b in result.geoms)


def test_separate_beyond_ratio_of_existing_bbox():
    # Arrange
    x = CHANGESET_NEW_BBOX_MIN_RATIO * 1.1
    existing_bounds = MultiPolygon([box(-1, -1, 0, 0)])
    p = Point(x, x)

    # Act
    result = extend_changeset_bounds(existing_bounds, [p])

    # Assert
    assert len(result.geoms) == 2
    assert any(b.bounds == (-1.0, -1.0, 0.0, 0.0) for b in result.geoms)
    assert any(b.bounds[0] == x and b.bounds[1] == x for b in result.geoms)


def test_fixed_k_clusters_produces_at_most_limit_when_many_points():
    # Arrange: more points than the bbox limit to force FIXED K-CLUSTERS
    pts = [Point(i * 10.0, 0.0) for i in range(CHANGESET_BBOX_LIMIT + 2)]

    # Act
    result = extend_changeset_bounds(MultiPolygon(), pts)

    # Assert: number of boxes never exceeds the limit and covers all points
    assert 1 <= len(result.geoms) <= CHANGESET_BBOX_LIMIT
    minx = min(p.x for p in pts)
    maxx = max(p.x for p in pts)
    rb = result.bounds
    assert rb[0] <= minx and rb[2] >= maxx
    assert rb[1] <= 0.0 and rb[3] >= 0.0


def test_limit_caps_when_adding_to_n_minus_one_boxes():
    # Arrange
    start = MultiPolygon([
        box(i * 10.0, 0.0, i * 10.0 + 1.0, 1.0) for i in range(CHANGESET_BBOX_LIMIT - 1)
    ])
    p = Point(CHANGESET_BBOX_LIMIT * 10.0, 0.0)

    # Act
    result = extend_changeset_bounds(start, [p])

    # Assert
    assert len(result.geoms) == CHANGESET_BBOX_LIMIT


def test_limit_does_not_exceed_when_already_at_limit():
    # Arrange
    start = MultiPolygon([
        box(i * 10.0, 0.0, i * 10.0 + 1.0, 1.0) for i in range(CHANGESET_BBOX_LIMIT)
    ])
    p = Point((CHANGESET_BBOX_LIMIT + 5) * 10.0, 0.0)

    # Act
    result = extend_changeset_bounds(start, [p])

    # Assert: still at most the limit, but may merge down
    assert 1 <= len(result.geoms) <= CHANGESET_BBOX_LIMIT
    rb = result.bounds
    sb = start.bounds
    assert rb[0] <= sb[0] and rb[2] >= max(sb[2], p.x)


@pytest.mark.parametrize(
    ('groups', 'per_group', 'spacing', 'expected_boxes'),
    [
        (5, 8, 1000.0, 5),
        (CHANGESET_BBOX_LIMIT, 6, 3000.0, CHANGESET_BBOX_LIMIT),
        (CHANGESET_BBOX_LIMIT + 5, 6, 3000.0, 1),
    ],
)
def test_fixed_k_clusters_widely_separated_groups(
    groups: int, per_group: int, spacing: float, expected_boxes: int
):
    # Arrange: far-separated groups
    pts = []
    for g in range(groups):
        base = g * spacing
        pts.extend(Point(base + 0.01 * j, 0.02 * j) for j in range(per_group))

    # Act
    result = extend_changeset_bounds(MultiPolygon(), pts)

    # Assert: count matches expectation; coverage spans full range
    assert len(result.geoms) == expected_boxes
    rb = result.bounds
    assert rb[0] <= 0.0 and rb[2] >= (groups - 1) * spacing

    # For cases where expected == groups, ensure boxes map to distinct groups
    if expected_boxes == groups:
        centers = [((b.bounds[0] + b.bounds[2]) / 2.0) for b in result.geoms]
        mapped_groups = {round(c / spacing) for c in centers}
        assert mapped_groups == set(range(groups))
