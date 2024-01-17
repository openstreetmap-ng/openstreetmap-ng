from sqlalchemy import Enum, ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.lib_cython.crypto import HASH_SIZE
from src.lib_cython.rich_text_mixin import RichTextMixin
from src.limits import REPORT_BODY_MAX_LENGTH
from src.models.db.base import Base
from src.models.db.cache_entry import CacheEntry
from src.models.db.created_at_mixin import CreatedAtMixin
from src.models.db.issue import Issue
from src.models.db.user import User
from src.models.report_category import ReportCategory
from src.models.text_format import TextFormat


class Report(Base.UUID, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'report'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    issue_id: Mapped[int] = mapped_column(ForeignKey(Issue.id), nullable=False)
    issue: Mapped[Issue] = relationship(lazy='raise')
    category: Mapped[ReportCategory] = mapped_column(Enum(ReportCategory), nullable=False)
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
        if len(value) > REPORT_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value
