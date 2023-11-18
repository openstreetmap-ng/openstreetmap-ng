from sqlalchemy import ForeignKey, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from lib.cache import CACHE_HASH_SIZE
from lib.rich_text import RichText
from limits import ISSUE_COMMENT_BODY_MAX_LENGTH
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.issue import Issue
from models.db.user import User
from models.text_format import TextFormat


class IssueComment(Base.UUID, CreatedAt):
    __tablename__ = 'issue_comment'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(lazy='raise')
    issue_id: Mapped[int] = mapped_column(ForeignKey(Issue.id), nullable=False)
    issue: Mapped[Issue] = relationship(back_populates='issue_comments', lazy='raise')
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None)

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > ISSUE_COMMENT_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value

    # TODO: SQL
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value
