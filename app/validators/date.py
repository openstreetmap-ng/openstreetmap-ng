import cython
from pydantic import BeforeValidator

from app.lib.date_utils import parse_date


@cython.cfunc
def _validate_date(value: str | None):
    return parse_date(value) if (value is not None) else None


DateValidator = BeforeValidator(_validate_date)
