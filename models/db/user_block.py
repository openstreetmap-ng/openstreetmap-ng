from datetime import datetime
from typing import Annotated

from annotated_types import MaxLen
from asyncache import cached
from pydantic import Field

from lib.rich_text import RichText
from limits import USER_BLOCK_BODY_MAX_LENGTH
from models.db.base_sequential import BaseSequential, SequentialId
from models.str import HexStr, NonEmptyStr
from models.text_format import TextFormat
from utils import utcnow


class UserBlock(BaseSequential):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    created_user_id: Annotated[SequentialId, Field(frozen=True)]
    expires_at: datetime | None
    awaits_acknowledgement: bool
    body: Annotated[NonEmptyStr, MaxLen(USER_BLOCK_BODY_MAX_LENGTH)]
    body_rich_hash: HexStr | None = None

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    updated_at: Annotated[datetime, Field(default_factory=utcnow)]
    revoked_at: datetime | None = None
    revoked_user_id: SequentialId | None = None

    @property
    def expired(self) -> bool:
        return (
            self.expires_at and
            self.expires_at < utcnow() and
            not self.awaits_acknowledgement
        )

    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value
