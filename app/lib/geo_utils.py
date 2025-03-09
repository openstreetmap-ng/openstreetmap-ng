from typing import overload

import cython
from h3 import compact_cells, geo_to_h3shape, h3shape_to_cells_experimental
from pyproj import Geod
from shapely import MultiPolygon, Point, Polygon, box, get_coordinates

from app.lib.exceptions_context import raise_for
from app.limits import GEO_COORDINATE_PRECISION
from app.validators.geometry import validate_geometry

if cython.compiled:
    from cython.cimports.libc.math import atan2, cos, log, log10, sin, sqrt
else:
    from math import atan2, cos, log, log10, sin, sqrt


@cython.cfunc
def _radians(degrees: cython.double) -> cython.double:
    return degrees * 0.017453292519943295  # pi / 180


def meters_to_radians(meters: float) -> float:
    """Convert a distance in meters to radians."""
    return meters / 6371000  # R


def radians_to_meters(radians: float) -> float:
    """Convert a distance in radians to meters."""
    return radians * 6371000  # R


def meters_to_degrees(meters: float) -> float:
    """Convert a distance in meters to degrees."""
    return meters / (6371000 / 57.29577951308232)  # R / (180 / pi)


def degrees_to_meters(degrees: float) -> float:
    """Convert a distance in degrees to meters."""
    return degrees * (6371000 / 57.29577951308232)  # R / (180 / pi)


def haversine_distance(p1: Point, p2: Point) -> float:
    """
    Calculate the distance between two points on the Earth's surface using the Haversine formula.

    Returns the distance in meters.
    """
    coords1 = get_coordinates(p1)[0].tolist()
    lon1: cython.double = coords1[0]
    lat1: cython.double = coords1[1]

    coords2 = get_coordinates(p2)[0].tolist()
    lon2: cython.double = coords2[0]
    lat2: cython.double = coords2[1]

    delta_lon: cython.double = _radians(lon2 - lon1)
    delta_lat: cython.double = _radians(lat2 - lat1)

    a = sin(delta_lat / 2) ** 2 + cos(_radians(lat1)) * cos(_radians(lat2)) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return c * 6371000  # R


@overload
def parse_bbox(s: str) -> Polygon | MultiPolygon: ...
@overload
def parse_bbox(s: None) -> None: ...
def parse_bbox(s: str | None) -> Polygon | MultiPolygon | None:
    """
    Parse a bbox string or bounds.

    Returns a Polygon or MultiPolygon (if crossing the antimeridian).

    Raises exception if the string is not in a valid format.

    >>> parse_bbox('1,2,3,4')
    POLYGON ((1 2, 1 4, 3 4, 3 2, 1 2))
    """
    if s is None:
        return None

    parts: list[str] = s.strip().split(',', 3)
    try:
        precision = GEO_COORDINATE_PRECISION
        minx: cython.double = round(float(parts[0].strip()), precision)
        miny: cython.double = round(float(parts[1].strip()), precision)
        maxx: cython.double = round(float(parts[2].strip()), precision)
        maxy: cython.double = round(float(parts[3].strip()), precision)
    except Exception:
        raise_for.bad_bbox(s)
    if minx > maxx:
        raise_for.bad_bbox(s, 'min longitude > max longitude')
    if miny > maxy:
        raise_for.bad_bbox(s, 'min latitude > max latitude')

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
        MultiPolygon(
            (
                box(minx, miny, 180, maxy),
                box(-180, miny, maxx - 360, maxy),
            )
        )
    )


def try_parse_point(lat_lon: str) -> Point | None:
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
                round(float(lon.strip()), GEO_COORDINATE_PRECISION),
                round(float(lat.strip()), GEO_COORDINATE_PRECISION),
            )
        )
    except Exception:
        return None


_GEOD = Geod(ellps='WGS84')


def polygon_to_h3(
    geometry: Polygon | MultiPolygon,
    *,
    balance_factor: float = 0.8,
    max_resolution: int = 15,
) -> list[str]:
    """
    Convert a Shapely Polygon/MultiPolygon to H3 cells with optimal resolution selection.
    Higher balance factors will result in more, finer cells.
    """
    h3_shape = geo_to_h3shape(geometry)

    # Calculate geodesic area
    area_m2: cython.double = _GEOD.geometry_area_perimeter(geometry)[0]
    area_m2 = abs(area_m2)
    area_km2 = area_m2 / 1e6

    resolution = _h3_optimal_resolution(area_km2, balance_factor, max_resolution)
    cells = h3shape_to_cells_experimental(h3_shape, resolution, contain='overlap')
    return compact_cells(cells)


@cython.cfunc
def _h3_optimal_resolution(
    area_km2: cython.double,
    balance_factor: cython.double,
    max_resolution: cython.int,
) -> int:
    """Calculate H3 resolution directly based on area and balance factor."""
    # Target cells - scaled by area logarithmically
    # Small areas get fewer cells, large areas get more cells proportionally
    log_area = log10(max(area_km2, 0.001))
    # Scale factor adjusts with balance_factor - higher balance = more cells
    scale_factor = 10 * (0.5 + balance_factor)
    target_cells = scale_factor * (1 + log_area)

    # Calculate total area to cover with hexagons
    # This includes an overlap factor that increases with balance_factor
    coverage_area = area_km2 * (1 + 0.5 * balance_factor)

    # Calculate area per cell to achieve target number of cells
    target_cell_area = coverage_area / target_cells

    # Calculate resolution directly based on cell area ratio
    # This uses the fact that each resolution step changes area by factor of ~7 (log(7) == 1.94591...)
    # Resolution 0 hexagon area is ~4.25M km2
    raw_resolution = log(4.25e6 / target_cell_area) / 1.9459101490553132

    # Apply balance factor adjustment
    final_resolution = raw_resolution + (balance_factor * 1.5 - 0.75)

    # Round and clamp to valid H3 resolution range
    return round(max(0, min(max_resolution, final_resolution)))
