from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import ForeignKey, LargeBinary, Sequence, Unicode, UnicodeText, update
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from config import SRID
from db import DB
from lib.cache import CACHE_HASH_SIZE
from lib.rich_text import RichText, rich_text_getter
from limits import DIARY_BODY_MAX_LENGTH, LANGUAGE_CODE_MAX_LENGTH
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.updated_at import UpdatedAt
from models.db.user import User
from models.text_format import TextFormat


class Diary(Base.Sequential, CreatedAt, UpdatedAt):
    __tablename__ = 'diary'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='diaries', lazy='raise')
    title: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None)
    language_code: Mapped[str] = mapped_column(Unicode(LANGUAGE_CODE_MAX_LENGTH), nullable=False)
    point: Mapped[WKBElement | None] = mapped_column(Geometry('POINT', SRID), nullable=True)

    # relationships (nested imports to avoid circular imports)
    from diary_comment import DiaryComment
    from diary_subscription import DiarySubscription

    diary_comments: Mapped[Sequence[DiaryComment]] = relationship(
        back_populates='diary', order_by='asc(DiaryComment.created_at)', lazy='raise'
    )
    diary_subscription_users: Mapped[Sequence[User]] = relationship(secondary=DiarySubscription, lazy='raise')

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > DIARY_BODY_MAX_LENGTH:
            raise ValueError('Diary is too long')
        return value

    body_rich = rich_text_getter('body', TextFormat.markdown)
