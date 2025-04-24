import numpy as np
import pytest
from shapely import Point, points

from app.config import GEO_COORDINATE_PRECISION
from app.lib.compressible_geometry import (
    compressible_geometry,
    point_to_compressible_wkb,
)


def test_compressible_geometry():
    rng = np.random.default_rng(42)
    coords = rng.random((32, 2), dtype=np.float64) * (360, 170) - (180, 85)
    coords = coords.round(GEO_COORDINATE_PRECISION)

    geoms: list[Point] = points(coords).tolist()  # type: ignore
    some_different = False

    for geom in geoms:
        processed = compressible_geometry(geom)
        assert processed.equals_exact(
            geom, tolerance=0.5 * 10**-GEO_COORDINATE_PRECISION
        )
        if not processed.equals(geom):
            some_different = True

    assert some_different, 'Compressible geometry must change the geometry'


@pytest.mark.parametrize(
    ('lon', 'lat', 'expected'),
    [
        (1, 2, '0101000000000000000000F03F0000000000000040'),
        (6317, -12, '01010000000000000000ADB84000000000000028C0'),
        (6317.57327358, -12.164174127, '0101000000000000C292ADB840000090A10E5428C0'),
    ],
)
def test_point_to_compressible_wkb(lon, lat, expected):
    assert point_to_compressible_wkb(lon, lat).hex().upper() == expected
