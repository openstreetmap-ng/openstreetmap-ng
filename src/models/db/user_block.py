from datetime import datetime

from sqlalchemy import Boolean, ColumnElement, DateTime, ForeignKey, LargeBinary, UnicodeText, and_, func, null, true
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.lib.crypto import HASH_SIZE
from src.lib.rich_text import RichTextMixin
from src.limits import USER_BLOCK_BODY_MAX_LENGTH
from src.models.db.base import Base
from src.models.db.cache_entry import CacheEntry
from src.models.db.created_at_mixin import CreatedAtMixin
from src.models.db.updated_at_mixin import UpdatedAtMixin
from src.models.db.user import User
from src.models.text_format import TextFormat
from src.utils import utcnow


class UserBlock(Base.Sequential, CreatedAtMixin, UpdatedAtMixin, RichTextMixin):
    __tablename__ = 'user_block'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    from_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    from_user: Mapped[User] = relationship(
        back_populates='user_blocks_given', foreign_keys=[from_user_id], lazy='raise'
    )
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(back_populates='user_blocks_received', foreign_keys=[to_user_id], lazy='raise')
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(LargeBinary(HASH_SIZE), nullable=True, default=None)
    body_rich: Mapped[CacheEntry | None] = relationship(
        CacheEntry,
        primaryjoin=CacheEntry.id == body_rich_hash,
        viewonly=True,
        default=None,
        lazy='raise',
    )

    # defaults
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    revoked_user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True, default=None)
    revoked_user: Mapped[User | None] = relationship(foreign_keys=[revoked_user_id], lazy='raise')

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > USER_BLOCK_BODY_MAX_LENGTH:
            raise ValueError('Comment is too long')
        return value

    @hybrid_property
    def expired(self) -> bool:
        return self.expires_at and self.expires_at < utcnow() and self.acknowledged

    @expired.inplace.expression
    @classmethod
    def _expired_expression(cls) -> ColumnElement[bool]:
        return and_(
            cls.expires_at != null(),
            cls.expires_at <= func.now(),
            cls.acknowledged == true(),
        )
