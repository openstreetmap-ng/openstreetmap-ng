from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from app.limits import USER_TOKEN_EMAIL_CHANGE_EXPIRE
from app.models.db.user_token import UserToken
from app.models.types import EmailType


class UserTokenEmailChange(UserToken):
    __tablename__ = 'user_token_email_change'
    __expire__ = USER_TOKEN_EMAIL_CHANGE_EXPIRE

    new_email: Mapped[EmailType] = mapped_column(Unicode(EMAIL_MAX_LENGTH), nullable=False)
