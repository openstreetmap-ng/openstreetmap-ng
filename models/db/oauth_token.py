from abc import ABC
from datetime import datetime
from typing import Annotated, Self

from pydantic import Field

from lib.crypto import hash_hex
from models.db.base import Base
from models.db.base_sequential import SequentialId
from models.scope import Scope
from models.str import HexStr
from utils import utcnow


class OAuthToken(Base, ABC):
    user_id: SequentialId | None
    application_id: Annotated[SequentialId, Field(frozen=True)]
    key_hashed: HexStr
    scopes: tuple[Scope, ...]

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    authorized_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def scopes_str(self) -> str:
        return ' '.join(sorted(self.scopes))

    @classmethod
    async def find_one_by_key(cls, key: str) -> Self | None:
        return await cls.find_one({'key_hashed': hash_hex(key, context=None)})
