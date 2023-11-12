from datetime import datetime

from asyncache import cached
from sqlalchemy import (Boolean, ColumnElement, DateTime, ForeignKey,
                        LargeBinary, UnicodeText, and_, func)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from lib.cache import CACHE_HASH_SIZE
from lib.rich_text import RichText
from limits import USER_BLOCK_BODY_MAX_LENGTH
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.updated_at import UpdatedAt
from models.db.user import User
from models.text_format import TextFormat
from utils import utcnow


class UserBlock(Base.Sequential, CreatedAt, UpdatedAt):
    __tablename__ = 'user_block'

    from_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    from_user: Mapped[User] = relationship(back_populates='user_blocks_given', foreign_keys=[from_user_id], lazy='raise')
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(back_populates='user_blocks_received', foreign_keys=[to_user_id], lazy='raise')
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(CACHE_HASH_SIZE), nullable=True, default=None)

    # defaults
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    revoked_user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True, default=None)
    revoked_user: Mapped[User | None] = relationship(foreign_keys=[revoked_user_id], lazy='raise')

    @validates('body')
    def validate_body(cls, key: str, value: str) -> str:
        if len(value) > USER_BLOCK_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value

    @hybrid_property
    def expired(self) -> bool:
        return (
            self.expires_at and
            self.expires_at < utcnow() and
            self.acknowledged
        )

    @expired.inplace.expression
    @classmethod
    def _expired_expression(cls) -> ColumnElement[bool]:
        return and_(
            cls.expires_at != None,
            cls.expires_at < func.now(),
            cls.acknowledged == True,
        )

    # TODO: SQL
    @cached({})
    async def body_rich(self) -> str:
        cache = await RichText.get_cache(self.body, self.body_rich_hash, TextFormat.markdown)
        if self.body_rich_hash != cache.id:
            self.body_rich_hash = cache.id
            await self.update()
        return cache.value
