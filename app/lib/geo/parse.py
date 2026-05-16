from typing import overload

import cython
from shapely import MultiPolygon, Point, Polygon, box

from app.exceptions.context import raise_for
from app.models.proto.shared_pb2 import Bounds as ProtoBounds
from app.validators.geometry import validate_geometry


@overload
def parse_bbox(
    s: str | tuple[float, float, float, float] | ProtoBounds, /
) -> Polygon | MultiPolygon: ...
@overload
def parse_bbox(s: None, /) -> None: ...
def parse_bbox(s: str | tuple[float, float, float, float] | ProtoBounds | None, /):
    """
    Parse a bbox string or bounds.

    Returns a Polygon or MultiPolygon (if crossing the antimeridian).

    Raises exception if the string is not in a valid format.

    >>> parse_bbox('1,2,3,4')
    POLYGON ((1 2, 1 4, 3 4, 3 2, 1 2))
    """
    if s is None:
        return None

    if isinstance(s, str):
        parts = s.split(',', 3)

        try:
            raw = (
                float(parts[0].strip()),
                float(parts[1].strip()),
                float(parts[2].strip()),
                float(parts[3].strip()),
            )
        except Exception:
            raise_for.bad_bbox(s)

    elif isinstance(s, ProtoBounds):
        raw = (s.min_lon, s.min_lat, s.max_lon, s.max_lat)
    else:
        raw = s

    minx = round(raw[0], 7)
    miny = round(raw[1], 7)
    maxx = round(raw[2], 7)
    maxy = round(raw[3], 7)

    if minx > maxx:
        raise_for.bad_bbox(
            f'{minx},{miny},{maxx},{maxy}', 'min longitude > max longitude'
        )
    if miny > maxy:
        raise_for.bad_bbox(
            f'{minx},{miny},{maxx},{maxy}', 'min latitude > max latitude'
        )

    # normalize latitude
    miny = max(miny, -90)
    maxy = min(maxy, 90)

    # special case, bbox wraps around the whole world
    if maxx - minx >= 360:
        return validate_geometry(box(-180, miny, 180, maxy))

    # normalize minx to [-180, 180), maxx to [minx, minx + 360)
    if minx < -180 or maxx > 180:
        offset: cython.double = ((minx + 180) % 360 - 180) - minx
        minx += offset
        maxx += offset

    # simple geometry, no meridian crossing
    if maxx <= 180:
        return validate_geometry(box(minx, miny, maxx, maxy))

    # meridian crossing
    return validate_geometry(
        MultiPolygon((
            box(minx, miny, 180, maxy),
            box(-180, miny, maxx - 360, maxy),
        ))
    )


def try_parse_point(lat_lon: str, /):
    """
    Try to parse a point string.

    Returns None if the string is not in a valid format.

    >>> try_parse_point('1,2')
    POINT (2 1)
    """
    lat, _, lon = lat_lon.partition(',')
    if not lon:
        lat, _, lon = lat_lon.partition(' ')
    if not lon:
        return None
    try:
        return validate_geometry(
            Point(
                round(float(lon.strip()), 7),
                round(float(lat.strip()), 7),
            )
        )
    except Exception:
        return None
