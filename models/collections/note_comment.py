from datetime import datetime
from typing import Annotated, Self

from asyncache import cached
from pydantic import Field, model_validator

from lib.rich_text import RichText
from limits import NOTE_COMMENT_BODY_MAX_LENGTH
from models.collections.base import _DEFAULT_FIND_LIMIT, Base
from models.collections.base_sequential import SequentialId
from models.note_event import NoteEvent
from models.str import HexStr, NonEmptyStr
from models.text_format import TextFormat
from utils import utcnow


class NoteComment(Base):
    user_id: Annotated[SequentialId | None, Field(frozen=True)]
    user_ip: Annotated[NonEmptyStr | None, Field(frozen=True)]
    event: Annotated[NoteEvent, Field(frozen=True)]
    body: Annotated[str, Field(frozen=True, max_length=NOTE_COMMENT_BODY_MAX_LENGTH)]
    body_rich_hash: HexStr | None = None

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    note_id: SequentialId | None = None

    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.plain)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()  # TODO: only selected fields
        return cache.value

    @model_validator(mode='after')
    def validate_user_id_user_ip(self) -> Self:
        # TODO: check if backwards compatible
        if self.user_id is None and self.user_ip is None:
            raise ValueError(f'{self.__class__.__qualname__} must have either a user_id or a user_ip')
        elif self.user_id is not None and self.user_ip is not None:
            raise ValueError(f'{self.__class__.__qualname__} cannot have both a user_id and a user_ip')
        return self

    def model_dump(self) -> dict:
        if not self.note_id:
            raise ValueError(f'{self.__class__.__qualname__} must have note id set to be dumped')
        return super().model_dump()

    @classmethod
    def find_many_by_note_id(cls, note_id: SequentialId, *, sort: dict | None = None, limit: int | None = _DEFAULT_FIND_LIMIT) -> list[Self]:
        return cls.find_many({'note_id': note_id}, sort=sort, limit=limit)
