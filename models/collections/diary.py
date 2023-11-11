from asyncache import cached
from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import ForeignKey, LargeBinary, Sequence, Unicode, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import SRID
from lib.rich_text import RichText
from limits import LANGUAGE_CODE_MAX_LENGTH
from models.collections.base import Base
from models.collections.created_at import CreatedAt
from models.collections.updated_at import UpdatedAt
from models.collections.user import User
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
    diary_comments: Mapped[Sequence[DiaryComment]] = relationship(back_populates='diary', lazy='raise')

    # TODO: SQL
    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value
