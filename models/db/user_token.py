from abc import ABC
from datetime import datetime
from typing import Annotated

from pydantic import Field

from models.db.base import Base
from models.db.base_sequential import SequentialId
from models.str import HexStr
from utils import utcnow


class UserToken(Base, ABC):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    expires_at: datetime
    key_hashed: Annotated[HexStr, Field(frozen=True)]

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    referrer: Annotated[str | None, Field(frozen=True)] = None
