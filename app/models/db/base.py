import re
from abc import ABC

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import BigInteger, Identity
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column
from zid import zid

from app.utils import unicode_normalize

_bad_xml_re = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F\uFFFE\uFFFF]')  # XML/1.0


class Base:
    class NoID(MappedAsDataclass, DeclarativeBase, kw_only=True):
        pass

    class Sequential(NoID):
        __abstract__ = True

        id: Mapped[int] = mapped_column(
            BigInteger,
            Identity(minvalue=1),
            init=False,
            nullable=False,
            primary_key=True,
        )

    class ZID(NoID):
        __abstract__ = True

        id: Mapped[int] = mapped_column(
            BigInteger,
            init=False,
            nullable=False,
            primary_key=True,
            default_factory=zid,
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
        )

        @classmethod
        @field_validator('*')
        def str_validator(cls, v):
            if isinstance(v, str) and v:
                # check for invalid XML/1.0 characters
                if _bad_xml_re.search(v):
                    raise ValueError(f'Invalid XML/1.0 characters in {v!r}')

                # normalize unicode to NFC form
                return unicode_normalize(v)
            return v
