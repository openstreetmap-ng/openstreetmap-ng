import math

import pytest
from shapely import MultiPolygon, Point, Polygon

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


def test_parse_bbox_simple():
    assert parse_bbox('-1,-2,3.3,4.4').equals(
        Polygon([(-1, -2), (3.3, -2), (3.3, 4.4), (-1, 4.4), (-1, -2)]),
    )


def test_parse_bbox_wrap_around():
    assert parse_bbox('-560,20,-550,30').equals(
        Polygon([(160, 20), (170, 20), (170, 30), (160, 30), (160, 20)]),
    )


def test_parse_bbox_cover_world():
    assert parse_bbox('100,20,900,30').equals(
        Polygon([(-180, 20), (180, 20), (180, 30), (-180, 30), (-180, 20)]),
    )


def test_parse_bbox_meridian():
    assert parse_bbox('175,10,195,20').equals(
        MultiPolygon(
            [
                Polygon([(175, 10), (180, 10), (180, 20), (175, 20), (175, 10)]),
                Polygon([(-180, 10), (-165, 10), (-165, 20), (-180, 20), (-180, 10)]),
            ]
        )
    )


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
        '1,-95,3,4',
        'a,b,c,d',
    ],
)
def test_parse_bbox_invalid(bbox):
    with pytest.raises(Exception):  # noqa: B017
        parse_bbox(bbox)
