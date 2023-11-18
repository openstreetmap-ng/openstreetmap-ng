from sqlalchemy import ForeignKey, LargeBinary, UnicodeText, update
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from db import DB
from lib.cache import CACHE_HASH_SIZE
from lib.rich_text import RichText, rich_text_getter
from limits import DIARY_COMMENT_BODY_MAX_LENGTH
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.diary import Diary
from models.db.user import User
from models.text_format import TextFormat


class DiaryComment(Base.UUID, CreatedAt):
    __tablename__ = 'diary_comment'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='diary_comments', lazy='raise')
    diary_id: Mapped[int] = mapped_column(ForeignKey(Diary.id), nullable=False)
    diary: Mapped[Diary] = relationship(back_populates='diary_comments', lazy='raise')
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None)

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > DIARY_COMMENT_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value

    body_rich = rich_text_getter('body', TextFormat.markdown)
