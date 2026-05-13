"""Tests for geometry validation, including null island rejection."""
import pytest
from shapely import Point

from app.validators.geometry import validate_geometry


def test_validate_geometry_normal_point():
    """Normal coordinates should pass validation."""
    result = validate_geometry(Point(1.0, 2.0))
    assert result is not None


def test_validate_geometry_null_island_rejected():
    """Null island (0, 0) should be rejected — always a bug in the editor."""
    with pytest.raises(Exception):  # APIError via raise_for
        validate_geometry(Point(0.0, 0.0))


def test_validate_geometry_near_null_island_accepted():
    """Coordinates very close to but not exactly null island should pass."""
    result = validate_geometry(Point(0.0000001, 0.0))
    assert result is not None

    result = validate_geometry(Point(0.0, 0.0000001))
    assert result is not None


def test_validate_geometry_out_of_bounds():
    """Out-of-bounds coordinates should be rejected (existing behavior)."""
    with pytest.raises(Exception):
        validate_geometry(Point(200.0, 100.0))

    with pytest.raises(Exception):
        validate_geometry(Point(-200.0, -100.0))
