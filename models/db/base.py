import re
from abc import ABC
from typing import Any, Generic, Self, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import BigInteger, Uuid
from sqlalchemy.orm import (DeclarativeBase, Mapped, MappedAsDataclass,
                            mapped_column)

from utils import unicode_normalize

_BAD_XML_RE = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F\uFFFE\uFFFF]')  # XML 1.0

T = TypeVar('T')


class Base(ABC):
    class NoID(DeclarativeBase, MappedAsDataclass, ABC):
        pass

    class Sequential(NoID, ABC):
        id: Mapped[int] = mapped_column(BigInteger, nullable=False, primary_key=True)

    class UUID(NoID, ABC):
        # TODO: sortable like timeflake or ulid if needed?
        id: Mapped[UUID] = mapped_column(Uuid, nullable=False, primary_key=True, default_factory=uuid4)

    class Validating(BaseModel, Generic[T], ABC):
        # use_enum_values=True is unpredictable
        # see https://github.com/pydantic/pydantic/issues/6565
        model_config = ConfigDict(
            allow_inf_nan=False,
            arbitrary_types_allowed=True,
            from_attributes=True,
            validate_assignment=True,
            validate_default=True)  # TODO: True only dev/test

        @field_validator('*')
        @classmethod
        def str_validator(cls, v: Any) -> Any:
            if isinstance(v, str) and v:
                # check for invalid XML 1.0 characters
                if _BAD_XML_RE.search(v):
                    raise ValueError(f'Invalid XML 1.0 characters {v!r}')

                # normalize unicode to NFC form
                return unicode_normalize(v)
            return v

        @classmethod
        def from_orm(cls, orm: T, *, validate: bool = True) -> Self:
            if validate:
                return cls.model_validate(orm)
            else:
                return cls.model_construct(orm)

        def to_orm(self) -> T:
            return T(**super().model_dump(by_alias=True))
