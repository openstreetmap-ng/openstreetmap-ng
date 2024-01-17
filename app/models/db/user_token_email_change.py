from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.user_token import UserToken


class UserTokenEmailChange(UserToken):
    __tablename__ = 'user_token_email_change'

    from_email: Mapped[str] = mapped_column(Unicode, nullable=False)
    to_email: Mapped[str] = mapped_column(Unicode, nullable=False)
