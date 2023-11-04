from abc import ABC
from typing import Annotated

from pydantic import Field

from models.collections.base import Base
from models.str import NonEmptyStr


class ACL(Base, ABC):
    restrictions: list[NonEmptyStr]

    _collection_name_: Annotated[str, Field(exclude=True, frozen=True)] = 'ACL'
