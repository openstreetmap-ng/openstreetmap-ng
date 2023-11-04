from datetime import datetime
from typing import Annotated, Self, Sequence

from asyncache import cached
from pydantic import Field

from lib.rich_text import RichText
from limits import CHANGESET_COMMENT_BODY_MAX_LENGTH
from models.collections.base import _DEFAULT_FIND_LIMIT, Base
from models.collections.base_sequential import SequentialId
from models.collections.user import User
from models.str import HexStr, NonEmptyStr
from models.text_format import TextFormat
from utils import utcnow


class ChangesetComment(Base):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    changeset_id: Annotated[SequentialId, Field(frozen=True)]
    body: Annotated[NonEmptyStr, Field(frozen=True, max_length=CHANGESET_COMMENT_BODY_MAX_LENGTH)]
    body_rich_hash: HexStr | None = None

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]

    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.plain)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value

    @classmethod
    async def find_many_by_changeset_id(cls, changeset_id: SequentialId, *, sort: dict | None = None, limit: int | None = _DEFAULT_FIND_LIMIT) -> Sequence[Self]:
        return await cls.find_many({'changeset_id': changeset_id}, sort=sort, limit=limit)

    @classmethod
    async def count_by_changeset_id(cls, changeset_id: SequentialId) -> int:
        return await cls.count({'changeset_id': changeset_id})
