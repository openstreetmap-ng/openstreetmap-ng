import re

import cython
from pydantic import BeforeValidator

_filename_re = re.compile(r'[^a-zA-Z0-9.]')

# TODO: test 255+ chars limit


@cython.cfunc
def _validate_filename(value: str) -> str:
    return _filename_re.sub('_', value)


FileNameValidator = BeforeValidator(_validate_filename)
