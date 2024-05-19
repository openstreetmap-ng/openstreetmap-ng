import cython
from pydantic import BeforeValidator

from app.lib.date_utils import parse_date


@cython.cfunc
def _validate_date(value: str | None):
    if value is None:
        return None
    return parse_date(value)


DateValidator = BeforeValidator(_validate_date)
