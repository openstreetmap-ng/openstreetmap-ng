from datetime import datetime

from sqlalchemy import Boolean, ColumnElement, ForeignKey, LargeBinary, UnicodeText, and_, func, null, true
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.lib.crypto import HASH_SIZE
from app.lib.date_utils import utcnow
from app.lib.rich_text import RichTextMixin, TextFormat
from app.limits import USER_BLOCK_BODY_MAX_LENGTH
from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.updated_at_mixin import UpdatedAtMixin
from app.models.db.user import User


class UserBlock(Base.Sequential, CreatedAtMixin, UpdatedAtMixin, RichTextMixin):
    __tablename__ = 'user_block'
    __rich_text_fields__ = (('body', TextFormat.markdown),)

    from_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    from_user: Mapped[User] = relationship(foreign_keys=(from_user_id,), lazy='raise', innerjoin=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(foreign_keys=(to_user_id,), lazy='raise', innerjoin=True)
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(True), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(HASH_SIZE),
        init=False,
        nullable=True,
        server_default=None,
    )

    # defaults
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(True), nullable=True, server_default=None)
    revoked_user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True, server_default=None)
    revoked_user: Mapped[User | None] = relationship(foreign_keys=(revoked_user_id,), lazy='raise')

    # runtime
    body_rich: str | None = None

    @validates('body')
    def validate_body(self, _: str, value: str) -> str:
        if len(value) > USER_BLOCK_BODY_MAX_LENGTH:
            raise ValueError(f'Comment body is too long ({len(value)} > {USER_BLOCK_BODY_MAX_LENGTH})')
        return value

    @hybrid_property
    def expired(self) -> bool:
        return (self.expires_at is not None) and (self.expires_at <= utcnow()) and self.acknowledged

    @expired.inplace.expression
    @classmethod
    def _expired_expression(cls) -> ColumnElement[bool]:
        return and_(
            cls.expires_at != null(),
            cls.expires_at <= func.statement_timestamp(),
            cls.acknowledged == true(),
        )
