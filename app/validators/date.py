from datetime import datetime

from pydantic import BeforeValidator

from app.lib.date_utils import parse_date


def _validate_date(value: str | None) -> datetime | None:
    return parse_date(value) if (value is not None) else None


DateValidator = BeforeValidator(_validate_date)
