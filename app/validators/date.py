from datetime import datetime

from pydantic import PlainValidator

from app.lib.date_utils import parse_date


def validate_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    return parse_date(value)


DateValidator = PlainValidator(validate_date)
