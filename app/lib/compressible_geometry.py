import struct
from typing import TypeVar, overload

import cython
import numpy as np
from numpy.typing import NDArray
from shapely import transform
from shapely.geometry.base import BaseGeometry

if cython.compiled:
    from cython.cimports.libc.math import ceil, log2
else:
    from math import ceil, log2

_GeomT = TypeVar('_GeomT', bound=BaseGeometry)


@cython.cfunc
def _create_mentissa_mask():
    max_number: cython.double = 180
    fractional_precision: cython.double = 7

    bits_for_precision: cython.size_t = int(  # noqa: RUF046
        ceil(log2(max_number * 10**fractional_precision) + 1)
    )

    full_mask: cython.size_t = (1 << 64) - 1
    zeros_mask: cython.size_t = (1 << (52 - bits_for_precision)) - 1

    return np.uint64(full_mask - zeros_mask)


_MASK: np.uint64 = _create_mentissa_mask()
_MASK_INT = int(_MASK)
_FLOAT_STRUCT = struct.Struct('<d')
_UINT64_STRUCT = struct.Struct('<Q')


@overload
def compressible_geometry(geometry: _GeomT, /) -> _GeomT: ...
@overload
def compressible_geometry(geometry: NDArray[np.float64], /) -> NDArray[np.float64]: ...
def compressible_geometry(
    geometry: _GeomT | NDArray[np.float64], /
) -> _GeomT | NDArray[np.float64]:
    """
    Make geometry easily compressible by reducing mentissa noise.
    It is then necessary to round the coordinates back.
    Inspired by http://www.danbaston.com/posts/2018/02/15/optimizing-postgis-geometries.html
    """
    if isinstance(geometry, BaseGeometry):
        return transform(geometry, compressible_geometry)
    view = geometry.view(np.uint64)
    view &= _MASK
    return geometry


@cython.cfunc
def _compressible_float(value: float):
    value_int: object = _UINT64_STRUCT.unpack(_FLOAT_STRUCT.pack(value))[0]
    return int(value_int) & _MASK_INT


_POINT_STRUCT = struct.Struct('<BIQQ')
_BBOX_STRUCT = struct.Struct('<BIII10Q')


def point_to_compressible_wkb(lon: float, lat: float):
    """Convert a coordinate pair to a compressible WKB hex format."""
    lon_int: object = _compressible_float(lon)
    lat_int: object = _compressible_float(lat)

    # (byte order 1 = little endian + geometry type 1 = Point)
    return _POINT_STRUCT.pack(1, 1, lon_int, lat_int)


def bbox_to_compressible_wkb(
    minlon: float, minlat: float, maxlon: float, maxlat: float
):
    """Convert a bounding box to a compressible WKB hex format."""
    minlon_int: object = _compressible_float(minlon)
    minlat_int: object = _compressible_float(minlat)
    maxlon_int: object = _compressible_float(maxlon)
    maxlat_int: object = _compressible_float(maxlat)

    # (byte order 1 = little endian + geometry type 3 = Polygon + 1 ring + 5 points)
    return _BBOX_STRUCT.pack(
        1,
        3,
        1,
        5,
        maxlon_int,
        minlat_int,
        maxlon_int,
        maxlat_int,
        minlon_int,
        maxlat_int,
        minlon_int,
        minlat_int,
        maxlon_int,
        minlat_int,
    )
