import math

import pytest
from shapely import Polygon
from shapely.geometry import Point

from app.lib.geo_utils import (
    haversine_distance,
    meters_to_radians,
    parse_bbox,
    radians_to_meters,
)

_earth_radius_meters = 6371000


@pytest.mark.parametrize(
    ('meters', 'radians'),
    [
        (0, 0),
        (_earth_radius_meters, 1),
        (_earth_radius_meters * math.pi, math.pi),
    ],
)
def test_meters_to_radians_and_back(meters, radians):
    assert math.isclose(meters_to_radians(meters), radians, rel_tol=1e-9)
    assert math.isclose(radians_to_meters(radians), meters, rel_tol=1e-9)


@pytest.mark.parametrize(
    ('p1', 'p2', 'expected_meters'),
    [
        (Point(0, 0), Point(0, 0), 0),
        (Point(0, 0), Point(0, 1), 111194.92664455873),  # about 111 km
        (Point(0, 0), Point(1, 0), 111194.92664455873),  # about 111 km
    ],
)
def test_haversine_distance(p1, p2, expected_meters):
    assert math.isclose(haversine_distance(p1, p2), expected_meters, rel_tol=1e-9)


@pytest.mark.parametrize(
    ('bbox', 'polygon'),
    [
        ('1,2,3,4', Polygon([(1, 2), (3, 2), (3, 4), (1, 4), (1, 2)])),
        ('-3,-4,-1,-2', Polygon([(-1, -2), (-3, -2), (-3, -4), (-1, -4), (-1, -2)])),
        ('-1,-2,3,4', Polygon([(-1, -2), (3, -2), (3, 4), (-1, 4), (-1, -2)])),
        ('1.1,2.2,3.3,4.4', Polygon([(1.1, 2.2), (3.3, 2.2), (3.3, 4.4), (1.1, 4.4), (1.1, 2.2)])),
    ],
)
def test_parse_bbox(bbox, polygon):
    assert parse_bbox(bbox).equals(polygon)


@pytest.mark.parametrize(
    'bbox',
    [
        '1,2,3',
        '1,2,1,2',
        '1,2,3,4,5',
        '3,2,1,4',
        '1,4,3,2',
        '190,2,3,4',
        '1,95,3,4',
        '-190,2,3,4',
        '1,-95,3,4',
        'a,b,c,d',
    ],
)
def test_parse_bbox_invalid(bbox):
    pytest.raises(Exception, parse_bbox, bbox)
