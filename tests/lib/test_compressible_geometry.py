import numpy as np
from shapely import Point, points

from app.lib.compressible_geometry import compressible_geometry
from app.limits import GEO_COORDINATE_PRECISION


def test_compressible_geometry():
    rng = np.random.default_rng(42)
    coords = rng.random((32, 2), dtype=np.float64) * (360, 170) - (180, 85)
    coords = coords.round(GEO_COORDINATE_PRECISION)
    geoms: list[Point] = points(coords).tolist()  # type: ignore
    some_different = False
    for geom in geoms:
        processed = compressible_geometry(geom)
        assert processed.equals_exact(geom, tolerance=0.5 * 10**-GEO_COORDINATE_PRECISION)
        if not processed.equals(geom):
            some_different = True
    assert some_different
