import re

from pydantic import BeforeValidator

_FILENAME_RE = re.compile(r'[^a-zA-Z0-9.]+')


def _validate_filename(value: str) -> str:
    return _FILENAME_RE.sub('_', value)


FileNameValidator = BeforeValidator(_validate_filename)
