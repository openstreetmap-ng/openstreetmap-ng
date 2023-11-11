from asyncache import cached
from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import ForeignKey, LargeBinary, Sequence, Unicode, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from config import SRID
from lib.rich_text import RichText
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
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)
    language_code: Mapped[str] = mapped_column(Unicode(LANGUAGE_CODE_MAX_LENGTH), nullable=False)
    point: Mapped[WKBElement | None] = mapped_column(Geometry('POINT', SRID), nullable=True)

    # relationships (nested imports to avoid circular imports)
    from diary_comment import DiaryComment
    diary_comments: Mapped[Sequence[DiaryComment]] = relationship(back_populates='diary', order_by='asc(DiaryComment.created_at)', lazy='raise')

    @validates('body')
    def validate_body(cls, key: str, value: str) -> str:
        if len(value) > DIARY_BODY_MAX_LENGTH:
            raise ValueError('Diary is too long')
        return value

    # TODO: SQL
    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value
