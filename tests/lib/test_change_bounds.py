from shapely import Point, box

from app.lib.changeset_bounds import extend_changeset_bounds
from app.limits import CHANGESET_NEW_BBOX_MIN_DISTANCE, CHANGESET_NEW_BBOX_MIN_RATIO
from app.models.db.changeset_bounds import ChangesetBounds


def test_change_bounds_points_merge():
    x = CHANGESET_NEW_BBOX_MIN_DISTANCE
    new_bounds = extend_changeset_bounds(
        (),
        (
            Point(0, 0),
            Point(x, x),
        ),
    )
    assert len(new_bounds) == 1
    assert new_bounds[0].bounds.bounds == (0, 0, x, x)


def test_change_bounds_points_separate():
    x = CHANGESET_NEW_BBOX_MIN_DISTANCE * 1.01
    new_bounds = extend_changeset_bounds(
        (),
        (
            Point(0, 0),
            Point(x, x),
        ),
    )
    assert len(new_bounds) == 2
    assert any(cb.bounds.bounds == (0, 0, 0, 0) for cb in new_bounds)
    assert any(cb.bounds.bounds == (x, x, x, x) for cb in new_bounds)


def test_change_bounds_early_merge():
    x = -CHANGESET_NEW_BBOX_MIN_DISTANCE
    y = CHANGESET_NEW_BBOX_MIN_RATIO * CHANGESET_NEW_BBOX_MIN_DISTANCE
    z = (CHANGESET_NEW_BBOX_MIN_RATIO + 1) * CHANGESET_NEW_BBOX_MIN_DISTANCE
    new_bounds = extend_changeset_bounds(
        (ChangesetBounds(bounds=box(x, x, 0, 0)),),
        (
            Point(y, y),
            Point(z, z),
        ),
    )
    assert len(new_bounds) == 1
    assert new_bounds[0].bounds.bounds == (x, x, z, z)


def test_change_bounds_early_separate():
    x = -CHANGESET_NEW_BBOX_MIN_DISTANCE
    y = CHANGESET_NEW_BBOX_MIN_RATIO * 1.01 * CHANGESET_NEW_BBOX_MIN_DISTANCE
    z = (CHANGESET_NEW_BBOX_MIN_RATIO * 1.01 + 1) * CHANGESET_NEW_BBOX_MIN_DISTANCE
    new_bounds = extend_changeset_bounds(
        (ChangesetBounds(bounds=box(x, x, 0, 0)),),
        (
            Point(y, y),
            Point(z, z),
        ),
    )
    assert len(new_bounds) == 2
    assert any(cb.bounds.bounds == (x, x, 0, 0) for cb in new_bounds)
    assert any(cb.bounds.bounds == (y, y, z, z) for cb in new_bounds)


def test_change_bounds_late_merge():
    x = CHANGESET_NEW_BBOX_MIN_RATIO
    new_bounds = extend_changeset_bounds(
        (ChangesetBounds(bounds=box(-1, -1, 0, 0)),),
        (Point(x, x),),
    )
    assert len(new_bounds) == 1
    assert new_bounds[0].bounds.bounds == (-1, -1, x, x)


def test_change_bounds_late_separate():
    x = CHANGESET_NEW_BBOX_MIN_RATIO * 1.01
    new_bounds = extend_changeset_bounds(
        (ChangesetBounds(bounds=box(-1, -1, 0, 0)),),
        (Point(x, x),),
    )
    assert len(new_bounds) == 2
    assert any(cb.bounds.bounds == (-1, -1, 0, 0) for cb in new_bounds)
    assert any(cb.bounds.bounds == (x, x, x, x) for cb in new_bounds)
