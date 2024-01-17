import cython

if cython.compiled:
    from cython.cimports.libc.math import log, pi, tan
else:
    from math import log, pi, tan


@cython.cfunc
def degrees(x: cython.double) -> cython.double:
    return x * (180 / pi)


@cython.cfunc
def radians(x: cython.double) -> cython.double:
    return x * (pi / 180)


@cython.cfunc
def x_sheet(lon: cython.double) -> cython.double:
    return lon


@cython.cfunc
def y_sheet(lat: cython.double) -> cython.double:
    return degrees(log(tan((radians(lat) / 2) + (pi / 4))))


# having a C-only class allows for better self. optimizations
@cython.final
@cython.cclass
class CMercator:
    _width: cython.int
    _height: cython.int
    _tx: cython.double
    _ty: cython.double
    _bx: cython.double
    _by: cython.double

    def __init__(
        self,
        min_lon: cython.double,
        min_lat: cython.double,
        max_lon: cython.double,
        max_lat: cython.double,
        width: cython.int,
        height: cython.int,
    ):
        min_lon_sheet = x_sheet(min_lon)
        max_lon_sheet = x_sheet(max_lon)
        min_lat_sheet = y_sheet(min_lat)
        max_lat_sheet = y_sheet(max_lat)

        x_size = max_lon_sheet - min_lon_sheet
        y_size = max_lat_sheet - min_lat_sheet
        x_scale = x_size / width
        y_scale = y_size / height
        scale = max(x_scale, y_scale)

        half_x_pad = ((width * scale) - x_size) / 2
        half_y_pad = ((height * scale) - y_size) / 2

        self._width = width
        self._height = height
        self._tx = min_lon_sheet - half_x_pad
        self._ty = min_lat_sheet - half_y_pad
        self._bx = max_lon_sheet + half_x_pad
        self._by = max_lat_sheet + half_y_pad

    def x(self, lon: cython.double) -> cython.double:
        if self._bx - self._tx <= 0:
            return self._width / 2
        return (x_sheet(lon) - self._tx) / (self._bx - self._tx) * self._width

    def y(self, lat: cython.double) -> cython.double:
        if self._by - self._ty <= 0:
            return self._height / 2
        return self._height - ((y_sheet(lat) - self._ty) / (self._by - self._ty) * self._height)


class Mercator:
    def __init__(
        self,
        min_lon: cython.double,
        min_lat: cython.double,
        max_lon: cython.double,
        max_lat: cython.double,
        width: cython.int,
        height: cython.int,
    ):
        self._impl = CMercator(min_lon, min_lat, max_lon, max_lat, width, height)

    def x(self, lon: cython.double) -> cython.double:
        return self._impl.x(lon)

    def y(self, lat: cython.double) -> cython.double:
        return self._impl.y(lat)
