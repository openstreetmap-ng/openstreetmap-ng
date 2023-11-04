from math import degrees, log, pi, radians, tan

_PI_4 = pi / 4


class Mercator:
    def __init__(self, min_lon: float, min_lat: float, max_lon: float, max_lat: float, width: float, height: float):
        min_lon_sheet = self.x_sheet(min_lon)
        max_lon_sheet = self.x_sheet(max_lon)
        min_lat_sheet = self.y_sheet(min_lat)
        max_lat_sheet = self.y_sheet(max_lat)

        x_size = max_lon_sheet - min_lon_sheet
        y_size = max_lat_sheet - min_lat_sheet
        x_scale = x_size / width
        y_scale = y_size / height
        scale = max(x_scale, y_scale)

        half_x_pad = ((width * scale) - x_size) / 2
        half_y_pad = ((height * scale) - y_size) / 2

        self.width = width
        self.height = height
        self.tx = min_lon_sheet - half_x_pad
        self.ty = min_lat_sheet - half_y_pad
        self.bx = max_lon_sheet + half_x_pad
        self.by = max_lat_sheet + half_y_pad

    def y_sheet(self, lat: float) -> float:
        return degrees(log(tan(_PI_4 + (radians(lat) / 2))))

    def x_sheet(self, lon: float) -> float:
        return lon

    def y(self, lat: float) -> float:
        if self.by - self.ty == 0:
            return self.height / 2
        return self.height - ((self.y_sheet(lat) - self.ty) / (self.by - self.ty) * self.height)

    def x(self, lon: float) -> float:
        if self.bx - self.tx == 0:
            return self.width / 2
        return (self.x_sheet(lon) - self.tx) / (self.bx - self.tx) * self.width
