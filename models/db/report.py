from datetime import datetime
from typing import Annotated

from annotated_types import MaxLen
from asyncache import cached
from pydantic import Field

from lib.rich_text import RichText
from limits import REPORT_BODY_MAX_LENGTH
from models.db.base import Base
from models.db.base_sequential import SequentialId
from models.report_category import ReportCategory
from models.str import HexStr, NonEmptyStr
from models.text_format import TextFormat
from utils import utcnow


class Report(Base):
    user_id: Annotated[SequentialId, Field(frozen=True)]
    issue_id: Annotated[SequentialId, Field(frozen=True)]
    category: Annotated[ReportCategory, Field(frozen=True)]
    body: Annotated[NonEmptyStr, Field(frozen=True, max_length=REPORT_BODY_MAX_LENGTH)]
    body_rich_hash: HexStr | None = None

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]

    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value
