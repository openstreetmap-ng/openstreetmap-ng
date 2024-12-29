import cython
import numpy as np
from numpy.typing import NDArray

if cython.compiled:
    from cython.cimports.libc.math import pi
else:
    from math import pi


def mercator(coords: NDArray[np.floating], width: cython.int, height: cython.int) -> NDArray[np.floating]:
    xs = coords[:, 0]
    ys = y_sheet(coords[:, 1])

    min_lon: cython.double = xs.min()
    max_lon: cython.double = xs.max()
    min_lat: cython.double = ys.min()
    max_lat: cython.double = ys.max()

    x_size = max_lon - min_lon
    y_size = max_lat - min_lat
    scale = max(x_size / width, y_size / height)

    half_x_pad = ((width * scale) - x_size) / 2
    half_y_pad = ((height * scale) - y_size) / 2

    tx = min_lon - half_x_pad
    ty = min_lat - half_y_pad
    bx = max_lon + half_x_pad
    by = max_lat + half_y_pad

    if bx - tx <= 0:
        x = np.full(coords.shape[0], width / 2, dtype=np.float64)
    else:
        x = (xs - tx) / (bx - tx) * width

    if by - ty <= 0:
        y = np.full(coords.shape[0], height / 2, dtype=np.float64)
    else:
        y = height - ((ys - ty) / (by - ty) * height)

    return np.column_stack((x, y))


@cython.cfunc
def y_sheet(arr: NDArray[np.floating]):
    return np.degrees(np.log(np.tan((np.radians(arr) / 2) + (pi / 4))))
