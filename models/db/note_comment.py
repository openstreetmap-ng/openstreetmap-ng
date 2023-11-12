from ipaddress import IPv4Address, IPv6Address
from typing import Self

from asyncache import cached
from pydantic import model_validator
from sqlalchemy import Enum, ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from lib.cache import CACHE_HASH_SIZE
from lib.rich_text import RichText
from limits import NOTE_COMMENT_BODY_MAX_LENGTH
from models.db.base import _DEFAULT_FIND_LIMIT, Base
from models.db.created_at import CreatedAt
from models.db.note import Note
from models.db.user import User
from models.note_event import NoteEvent
from models.text_format import TextFormat


class NoteComment(Base.UUID, CreatedAt):
    __tablename__ = 'note_comment'

    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(back_populates='note_comments', lazy='raise')
    user_ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET, nullable=True)
    note_id: Mapped[int] = mapped_column(ForeignKey(Note.id), nullable=False)
    note: Mapped[Note] = relationship(back_populates='note_comments', lazy='raise')
    event: Mapped[NoteEvent] = mapped_column(Enum(NoteEvent), nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None)

    @validates('body')
    def validate_body(cls, key: str, value: str) -> str:
        if len(value) > NOTE_COMMENT_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value

    # TODO: SQL
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
