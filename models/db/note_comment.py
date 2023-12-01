from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import Enum, ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from services.cache_service import CACHE_HASH_SIZE
from lib.rich_text import rich_text_getter
from limits import NOTE_COMMENT_BODY_MAX_LENGTH
from models.db.base import Base
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
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > NOTE_COMMENT_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value

    body_rich = rich_text_getter('body', TextFormat.plain)
