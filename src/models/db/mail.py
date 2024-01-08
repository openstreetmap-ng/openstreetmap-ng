from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, SmallInteger, UnicodeText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.created_at_mixin import CreatedAtMixin
from src.models.db.user import User
from src.models.mail_from_type import MailFromType


class Mail(Base.UUID, CreatedAtMixin):
    __tablename__ = 'mail'

    from_user_id: Mapped[int | None] = mapped_column(ForeignKey(User.id), nullable=True)
    from_user: Mapped[User | None] = relationship(lazy='joined')
    from_type: Mapped[MailFromType] = mapped_column(Enum(MailFromType), nullable=False)
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(lazy='joined')
    subject: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    body: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    ref: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # defaults
    processing_counter: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    processing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
