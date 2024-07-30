from sqlalchemy import ForeignKey, Index, LargeBinary, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.lib.crypto import HASH_SIZE
from app.lib.rich_text import RichTextMixin, TextFormat
from app.models.db.base import Base
from app.models.db.changeset import Changeset
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.user import User


class ChangesetComment(Base.Sequential, CreatedAtMixin, RichTextMixin):
    __tablename__ = 'changeset_comment'
    __rich_text_fields__ = (('body', TextFormat.plain),)

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(init=False, lazy='raise', innerjoin=True)
    changeset_id: Mapped[int] = mapped_column(ForeignKey(Changeset.id, ondelete='CASCADE'), nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body_rich_hash: Mapped[bytes | None] = mapped_column(
        LargeBinary(HASH_SIZE),
        init=False,
        nullable=True,
        server_default=None,
    )

    # runtime
    body_rich: str | None = None

    __table_args__ = (Index('changeset_comment_idx', changeset_id, 'created_at'),)
