from typing import Annotated

import cython
from annotated_types import MaxLen, MinLen
from pydantic import AfterValidator, TypeAdapter
from sizestr import sizestr

from app.config import PYDANTIC_CONFIG, TAGS_KEY_MAX_LENGTH, TAGS_LIMIT, TAGS_MAX_SIZE
from app.validators.unicode import UnicodeValidator
from app.validators.xml import XMLSafeValidator


def _validate_tags(
    v: dict[str, str],
    *,
    TAGS_LIMIT: cython.size_t = TAGS_LIMIT,
    TAGS_MAX_SIZE: cython.size_t = TAGS_MAX_SIZE,
    TAGS_MAX_LEN_SAFE_SIZE: cython.size_t = (
        TAGS_MAX_SIZE // (TAGS_KEY_MAX_LENGTH + 255)
    ),
):
    num_tags: cython.size_t = len(v)

    if num_tags > TAGS_LIMIT:
        raise ValueError(f'Cannot have more than {TAGS_LIMIT} tags')

    if num_tags > TAGS_MAX_LEN_SAFE_SIZE:
        size: cython.size_t = 0
        for key, value in v.items():
            size += len(key) + len(value)
            if size > TAGS_MAX_SIZE:
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
