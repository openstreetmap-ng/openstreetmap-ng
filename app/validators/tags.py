from typing import Annotated

import cython
from annotated_types import MaxLen, MinLen
from pydantic import AfterValidator, TypeAdapter
from sizestr import sizestr

from app.config import PYDANTIC_CONFIG
from app.limits import TAGS_KEY_MAX_LENGTH, TAGS_LIMIT, TAGS_MAX_SIZE
from app.validators.unicode import UnicodeValidator
from app.validators.xml import XMLSafeValidator

_MIN_TAGS_LEN_TO_EXCEED_SIZE = TAGS_MAX_SIZE / (TAGS_KEY_MAX_LENGTH + 255)


def _validate_tags(v: dict[str, str]) -> dict[str, str]:
    num_tags: int = len(v)

    if num_tags > TAGS_LIMIT:
        raise ValueError(f'Cannot have more than {TAGS_LIMIT} tags')

    if num_tags > _MIN_TAGS_LEN_TO_EXCEED_SIZE:
        size: cython.Py_ssize_t = 0
        limit: cython.Py_ssize_t = TAGS_MAX_SIZE
        for key, value in v.items():
            size += len(key) + len(value)
            if size > limit:
                raise ValueError(f'Tags size cannot exceed {sizestr(TAGS_MAX_SIZE)}')

    return v


TagsValidating = Annotated[
    dict[
        Annotated[
            str,
            UnicodeValidator,
            MinLen(1),
            MaxLen(TAGS_KEY_MAX_LENGTH),
            XMLSafeValidator,
        ],
        Annotated[
            str,
            UnicodeValidator,
            MinLen(1),
            MaxLen(255),
            XMLSafeValidator,
        ],
    ],
    AfterValidator(_validate_tags),
]

# TODO: check use
TagsValidator = TypeAdapter(TagsValidating, config=PYDANTIC_CONFIG)
