import cython
from h3 import (
    cell_to_parent,
    compact_cells,
    geo_to_h3shape,
    h3shape_to_cells_experimental,
)
from pyproj import Geod
from shapely import MultiPolygon, Polygon

if cython.compiled:
    from cython.cimports.libc.math import log, log10
else:
    from math import log, log10

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
    max_resolution: cython.size_t,
):
    """Calculate H3 resolution directly based on area and balance factor."""
    # Target cells - scaled by area logarithmically
    # Small areas get fewer cells, large areas get more cells proportionally
    log_area = log10(max(area_km2, 0.001))
    # Scale factor adjusts with balance_factor - higher balance = more cells
    scale_factor = 10 * (0.5 + balance_factor)
    target_cells = scale_factor * (1 + log_area)
    if target_cells < 1:
        return max_resolution

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


def polygon_to_h3_search(area: Polygon | MultiPolygon, resolution: int) -> list[str]:
    """Return covering H3 cells plus their parents for the given polygon."""
    cells = set(
        h3shape_to_cells_experimental(
            geo_to_h3shape(area), resolution, contain='overlap'
        )
    )
    for cell in tuple(cells):
        cells.update(cell_to_parent(cell, res) for res in range(resolution))
    return list(cells)
