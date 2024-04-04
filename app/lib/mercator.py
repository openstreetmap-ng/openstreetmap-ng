import cython
import numpy as np

if cython.compiled:
    from cython.cimports.libc.math import pi
else:
    from math import pi


@cython.cfunc
def y_sheet(arr: np.ndarray) -> np.ndarray:
    return np.degrees(np.log(np.tan((np.radians(arr) / 2) + (pi / 4))))


def mercator(
    coords: np.ndarray,
    width: cython.int,
    height: cython.int,
) -> np.ndarray:
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
        x = np.full(coords.shape[0], width / 2)
    else:
        x = (xs - tx) / (bx - tx) * width

    if by - ty <= 0:
        y = np.full(coords.shape[0], height / 2)
    else:
        y = height - ((ys - ty) / (by - ty) * height)

    return np.column_stack((x, y))
