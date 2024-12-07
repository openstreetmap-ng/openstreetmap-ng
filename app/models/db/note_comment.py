import enum
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import Computed, Enum, ForeignKey, Index, LargeBinary, UnicodeText
from sqlalchemy.dialects.postgresql import INET, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.lib.crypto import HASH_SIZE
from app.lib.rich_text import RichTextMixin, TextFormat
from app.limits import NOTE_COMMENT_BODY_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.note import Note
from app.models.db.user import User


class NoteEvent(str, enum.Enum):
    opened = 'opened'
    closed = 'closed'
    reopened = 'reopened'
    commented = 'commented'
    hidden = 'hidden'


class NoteComment(Base.Sequential, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'note_comment'
    __rich_text_fields__ = (('body', TextFormat.plain),)

    # TODO: will joinedload work with None?
    user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    user: Mapped[User | None] = relationship(init=False, lazy='raise')
    user_ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET, nullable=True)
    note_id: Mapped[int] = mapped_column(ForeignKey(Note.id), nullable=False)
    event: Mapped[NoteEvent] = mapped_column(Enum(NoteEvent), nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(HASH_SIZE),
        init=False,
        nullable=True,
        server_default=None,
    )
    body_tsvector: Mapped = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', body)", persisted=True),
        init=False,
        nullable=False,
    )

    # runtime
    body_rich: str | None = None
    legacy_note: Note | None = None

    __table_args__ = (
        Index('note_comment_note_created_idx', note_id, 'created_at'),
        Index('note_comment_event_user_id_idx', event, user_id, 'id'),
        Index('note_comment_body_idx', body_tsvector, postgresql_using='gin'),
    )

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > NOTE_COMMENT_BODY_MAX_LENGTH:
            raise ValueError(f'Comment body is too long ({len(value)} > {NOTE_COMMENT_BODY_MAX_LENGTH})')
        return value
