from sqlalchemy import ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.lib.crypto import HASH_SIZE
from app.lib.rich_text import RichTextMixin, TextFormat
from app.limits import DIARY_COMMENT_BODY_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.diary import Diary
from app.models.db.user import User


class DiaryComment(Base.ZID, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'diary_comment'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(init=False, lazy='raise', innerjoin=True)
    diary_id: Mapped[int] = mapped_column(ForeignKey(Diary.id), nullable=False)
    diary: Mapped[Diary] = relationship(init=False, lazy='raise', innerjoin=True)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(HASH_SIZE),
        init=False,
        nullable=True,
        server_default=None,
    )

    # runtime
    body_rich: str | None = None

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > DIARY_COMMENT_BODY_MAX_LENGTH:
            raise ValueError(f'Comment body is too long ({len(value)} > {DIARY_COMMENT_BODY_MAX_LENGTH})')
        return value
