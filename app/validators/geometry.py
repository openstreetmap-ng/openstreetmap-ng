from pydantic import PlainValidator

from app.lib_cython.geo_utils import validate_geometry

GeometryValidator = PlainValidator(validate_geometry)
