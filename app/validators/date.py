from datetime import datetime

from pydantic import BeforeValidator

from app.lib.date_utils import parse_date


def _validate_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    return parse_date(value)


DateValidator = BeforeValidator(_validate_date)
