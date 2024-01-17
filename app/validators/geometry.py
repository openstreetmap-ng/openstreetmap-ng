from pydantic import PlainValidator

from app.libc.geo_utils import validate_geometry

GeometryValidator = PlainValidator(validate_geometry)
