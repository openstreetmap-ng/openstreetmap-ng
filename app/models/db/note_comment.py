from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import Enum, ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.config import APP_URL
from app.libc.crypto import HASH_SIZE
from app.libc.rich_text_mixin import RichTextMixin
from app.limits import NOTE_COMMENT_BODY_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.cache_entry import CacheEntry
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.note import Note
from app.models.db.user import User
from app.models.note_event import NoteEvent
from app.models.text_format import TextFormat


class NoteComment(Base.UUID, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'note_comment'
    __rich_text_fields__ = (('body', TextFormat.plain),)

    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(lazy='raise')
    user_ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET, nullable=True)
    note_id: Mapped[int] = mapped_column(ForeignKey(Note.id), nullable=False)
    note: Mapped[Note] = relationship(back_populates='comments', lazy='raise')
    event: Mapped[NoteEvent] = mapped_column(Enum(NoteEvent), nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(HASH_SIZE), nullable=True, default=None)
    body_rich: Mapped[CacheEntry | None] = relationship(
        CacheEntry,
        primaryjoin=CacheEntry.id == body_rich_hash,
        viewonly=True,
        default=None,
        lazy='raise',
    )

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > NOTE_COMMENT_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value

    @property
    def legacy_permalink(self) -> str:
        """
        Get the note comment's legacy permalink.

        >>> note_comment.legacy_permalink
        'https://www.openstreetmap.org/note/123456#c123456'
        """

        return f'{APP_URL}/note/{self.note_id}#c{self.id}'
