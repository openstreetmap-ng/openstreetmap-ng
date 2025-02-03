from typing import Annotated

import cython
from annotated_types import MaxLen
from pydantic import field_validator
from sizestr import sizestr

from app.limits import ELEMENT_TAGS_KEY_MAX_LENGTH, ELEMENT_TAGS_LIMIT, ELEMENT_TAGS_MAX_SIZE
from app.models.db.base import Base

_min_tags_len_to_exceed_size = ELEMENT_TAGS_MAX_SIZE / (ELEMENT_TAGS_KEY_MAX_LENGTH + 255)


class TagsValidating(Base.Validating):
    tags: dict[Annotated[str, MaxLen(ELEMENT_TAGS_KEY_MAX_LENGTH)], Annotated[str, MaxLen(255)]]

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, tags: dict[str, str]) -> dict[str, str]:
        tags_len = len(tags)

        if tags_len > ELEMENT_TAGS_LIMIT:
            raise ValueError(f'Element cannot have more than {ELEMENT_TAGS_LIMIT} tags')
        if tags_len > _min_tags_len_to_exceed_size:
            size: cython.int = 0
            for key, value in tags.items():
                size += len(key) + len(value)
                if size > ELEMENT_TAGS_MAX_SIZE:
                    raise ValueError(f'Element tags size cannot exceed {sizestr(ELEMENT_TAGS_MAX_SIZE)}')

        return tags
