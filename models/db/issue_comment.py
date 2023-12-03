from sqlalchemy import ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from lib.rich_text import RichTextMixin
from limits import ISSUE_COMMENT_BODY_MAX_LENGTH
from models.db.base import Base
from models.db.cache_entry import CacheEntry
from models.db.created_at import CreatedAt
from models.db.issue import Issue
from models.db.user import User
from models.text_format import TextFormat
from services.cache_service import CACHE_HASH_SIZE


class IssueComment(Base.UUID, CreatedAt, RichTextMixin):
    __tablename__ = 'issue_comment'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    issue_id: Mapped[int] = mapped_column(ForeignKey(Issue.id), nullable=False)
    issue: Mapped[Issue] = relationship(back_populates='comments', lazy='raise')
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None)
    body_rich: Mapped[CacheEntry | None] = relationship(
        CacheEntry,
        primaryjoin=CacheEntry.id == body_rich_hash,
        viewonly=True,
        default=None,
        lazy='raise',
    )

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > ISSUE_COMMENT_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value
