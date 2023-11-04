from abc import ABC
from datetime import datetime
from typing import Annotated, Self

from pydantic import Field

from lib.crypto import decrypt_hex
from models.collections.base_sequential import BaseSequential, SequentialId
from models.scope import Scope
from models.str import HexStr, NonEmptyStr
from utils import updating_cached_property, utcnow


class OAuthApplication(BaseSequential, ABC):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    name: NonEmptyStr
    key_public: NonEmptyStr
    key_secret_encrypted: HexStr
    scopes: tuple[Scope, ...]

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    updated_at: Annotated[datetime, Field(default_factory=utcnow)]

    _collection_name_: Annotated[str, Field(exclude=True, frozen=True)] = 'OAuthApplication'

    @updating_cached_property(lambda self: self.key_secret_encrypted)
    def key_secret(self) -> str:
        return decrypt_hex(self.key_secret_encrypted)

    @classmethod
    async def find_one_by_key(cls, key: str) -> Self | None:
        return await cls.find_one({'key_public': key})
