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
    tags_len = len(v)

    if tags_len > TAGS_LIMIT:
        raise ValueError(f'Cannot have more than {TAGS_LIMIT} tags')
    if tags_len > _MIN_TAGS_LEN_TO_EXCEED_SIZE:
        size: cython.int = 0
        limit: cython.int = TAGS_MAX_SIZE
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

TagsValidator = TypeAdapter(TagsValidating, config=PYDANTIC_CONFIG)
