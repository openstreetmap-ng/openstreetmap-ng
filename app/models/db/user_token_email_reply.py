from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.user import User
from app.models.db.user_token import UserToken
from app.models.mail_source import MailSource


class UserTokenEmailReply(UserToken):
    __tablename__ = 'user_token_email_reply'

    mail_source: Mapped[MailSource] = mapped_column(Enum(MailSource), nullable=False)
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(foreign_keys=(to_user_id,), lazy='joined', innerjoin=True)
