import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, SmallInteger, UnicodeText
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base
from app.models.db.created_at_mixin import CreatedAtMixin
from app.models.db.user import User


class MailSource(str, enum.Enum):
    system = 'system'
    message = 'message'
    diary_comment = 'diary_comment'


class Mail(Base.ZID, CreatedAtMixin):
    __tablename__ = 'mail'

    source: Mapped[MailSource] = mapped_column(Enum(MailSource), nullable=False)
    from_user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    from_user: Mapped[User | None] = relationship(foreign_keys=(from_user_id,), init=False, lazy='raise')
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(foreign_keys=(to_user_id,), init=False, lazy='raise', innerjoin=True)
    subject: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    ref: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # defaults
    processing_counter: Mapped[int] = mapped_column(
        SmallInteger,
        init=False,
        nullable=False,
        server_default='0',
    )
    processing_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(True),
        init=False,
        nullable=True,
        server_default=None,
    )

    __table_args__ = (Index('mail_processing_at_idx', processing_at),)
