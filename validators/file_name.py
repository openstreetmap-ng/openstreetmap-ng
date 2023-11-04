import re

from pydantic import PlainValidator

_file_name_re = re.compile(r'[^a-zA-Z0-9.]')


# TODO: test 255+ chars limit
def validate_file_name(value: str) -> str:
    return _file_name_re.sub('_', value)


FileNameValidator = PlainValidator(validate_file_name)
