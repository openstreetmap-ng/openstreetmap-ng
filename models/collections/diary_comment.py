from asyncache import cached
from sqlalchemy import ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.rich_text import RichText
from models.collections.base import Base
from models.collections.created_at import CreatedAt
from models.collections.diary import Diary
from models.collections.user import User
from models.text_format import TextFormat


class DiaryComment(Base.UUID, CreatedAt):
    __tablename__ = 'diary_comment'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='diary_comments', lazy='raise')
    diary_id: Mapped[int] = mapped_column(ForeignKey(Diary.id), nullable=False)
    diary: Mapped[Diary] = relationship(back_populates='diary_comments', lazy='raise')
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)

    # TODO: SQL
    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value
