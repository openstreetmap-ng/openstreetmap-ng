from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.user import User
from app.models.db.user_token import UserToken
from app.models.mail_from_type import MailFromType


class UserTokenEmailReply(UserToken):
    __tablename__ = 'user_token_email_reply'

    source_type: Mapped[MailFromType] = mapped_column(Enum(MailFromType), nullable=False)
    to_user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    to_user: Mapped[User] = relationship(lazy='joined')
