from pydantic import PlainValidator
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from lib.exceptions import raise_for


def validate_geometry(value: dict | BaseGeometry) -> BaseGeometry:
    if isinstance(value, dict):
        value = shape(value)
    if not value.is_valid:
        raise_for().bad_geometry()
    for lon, lat in value.coords:
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise_for().bad_geometry_coordinates(lon, lat)
            # TODO: 0.7:
            # raise ValueError(f'Invalid coordinates {lon=!r} {lat=!r}. '
            #                  f'Please ensure longitude and latitude are in the EPSG:4326/WGS84 format.')
    return value


GeometryValidator = PlainValidator(validate_geometry)
