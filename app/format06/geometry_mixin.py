from shapely import Point

from app.lib.xmltodict import xattr


class Geometry06Mixin:
    @staticmethod
    def encode_point(point: Point | None) -> dict:
        """
        >>> encode_point(Point(1, 2))
        {'@lon': 1, '@lat': 2}
        """

        if point is None:
            return {}

        return {
            xattr('lon'): point.x,
            xattr('lat'): point.y,
        }

    @staticmethod
    def decode_point_unsafe(data: dict) -> Point | None:
        """
        This method does not validate the input data.

        >>> decode_point_unsafe({'@lon': '1', '@lat': '2'})
        POINT (1 2)
        """

        if (lon := data.get('@lon')) is None or (lat := data.get('@lat')) is None:
            return None

        return Point(
            float(lon),
            float(lat),
        )
