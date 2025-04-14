from typing import TypeVar, overload

import cython
import numpy as np
from numpy.typing import NDArray
from shapely import transform
from shapely.geometry.base import BaseGeometry

from app.config import GEO_COORDINATE_PRECISION

if cython.compiled:
    from cython.cimports.libc.math import ceil, log2
else:
    from math import ceil, log2

_GeomT = TypeVar('_GeomT', bound=BaseGeometry)


@cython.cfunc
def _create_mentissa_mask():
    max_number: cython.double = 180
    fractional_precision: cython.double = GEO_COORDINATE_PRECISION

    bits_for_precision: cython.ulonglong = int(  # noqa: RUF046
        ceil(log2(max_number * 10**fractional_precision) + 1)
    )

    full_mask: cython.ulonglong = (1 << 64) - 1
    zeros_mask: cython.ulonglong = (1 << (52 - bits_for_precision)) - 1

    return np.uint64(full_mask - zeros_mask)


_MASK: np.uint64 = _create_mentissa_mask()


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
