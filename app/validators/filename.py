import re

import cython
from pydantic import PlainValidator

_filename_re = re.compile(r'[^a-zA-Z0-9.]')

# TODO: test 255+ chars limit


@cython.cfunc
def _validate_filename(value: str) -> str:
    return _filename_re.sub('_', value)


FileNameValidator = PlainValidator(_validate_filename)
