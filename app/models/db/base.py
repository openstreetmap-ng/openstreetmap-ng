import re
from abc import ABC
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import BigInteger, Identity, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

from app.utils import unicode_normalize

_bad_xml_re = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F\uFFFE\uFFFF]')  # XML 1.0


class Base:
    class NoID(MappedAsDataclass, DeclarativeBase, kw_only=True):
        pass

    class Sequential(NoID):
        __abstract__ = True

        id: Mapped[int] = mapped_column(
            BigInteger,
            # always=False: during future migration, ids will be set explicitly
            Identity(always=False, minvalue=1),
            init=False,
            nullable=False,
            primary_key=True,
        )

    class UUID(NoID):
        __abstract__ = True

        id: Mapped[UUID] = mapped_column(
            Uuid,
            init=False,
            nullable=False,
            primary_key=True,
            server_default=func.gen_random_uuid(),
        )

    class Validating(BaseModel, ABC):
        # use_enum_values=True is unpredictable
        # see https://github.com/pydantic/pydantic/issues/6565
        model_config = ConfigDict(
            allow_inf_nan=False,
            arbitrary_types_allowed=True,
            from_attributes=True,
            validate_assignment=True,
            validate_default=True,
        )  # TODO: True only dev/test

        @field_validator('*')
        @classmethod
        def str_validator(cls, v):
            if isinstance(v, str) and v:
                # check for invalid XML 1.0 characters
                if _bad_xml_re.search(v):
                    raise ValueError(f'Invalid XML 1.0 characters {v!r}')

                # normalize unicode to NFC form
                return unicode_normalize(v)
            return v

        @classmethod
        def from_orm(cls, orm, *, validate: bool = True) -> Self:
            if validate:
                return cls.model_validate(orm)
            else:
                return cls.model_construct(orm)

        def to_orm_dict(self) -> dict:
            return super().model_dump(by_alias=True)
