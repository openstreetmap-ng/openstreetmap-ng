from typing import Annotated, Self

from pydantic import Field, model_validator

from models.collections.base import Base
from models.collections.base_sequential import SequentialId


class Friendship(Base):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    friend_user_id: Annotated[SequentialId, Field(frozen=True)]

    @model_validator(mode='after')
    def validate_not_self(self) -> Self:
        if self.user_id == self.friend_user_id:
            raise ValueError(f'{self.__class__.__qualname__} cannot be between the same user')
        return self

    @classmethod
    async def find_one_by_users(cls, user_id: SequentialId, friend_user_id: SequentialId) -> Self | None:
        return await cls.find_one({
            'user_id': user_id,
            'friend_user_id': friend_user_id,
        })
