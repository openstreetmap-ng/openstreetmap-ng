from email_validator.rfc_constants import EMAIL_MAX_LENGTH
from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.user_token import UserToken
from app.models.types import EmailType


class UserTokenEmailChange(UserToken):
    __tablename__ = 'user_token_email_change'

    new_email: Mapped[EmailType] = mapped_column(Unicode(EMAIL_MAX_LENGTH), nullable=False)
