from datetime import datetime
from typing import Annotated

from annotated_types import MaxLen
from asyncache import cached
from pydantic import Field

from lib.rich_text import RichText
from limits import DIARY_ENTRY_BODY_MAX_LENGTH
from models.collections.base_sequential import BaseSequential, SequentialId
from models.geometry import PointGeometry
from models.str import HexStr, NonEmptyStr, Str255
from models.text_format import TextFormat
from utils import utcnow


class DiaryEntry(BaseSequential):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    title: Str255
    body: Annotated[NonEmptyStr, MaxLen(DIARY_ENTRY_BODY_MAX_LENGTH)]
    body_rich_hash: HexStr | None = None
    language_code: str
    point: PointGeometry | None

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    updated_at: Annotated[datetime, Field(default_factory=utcnow)]

    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value
