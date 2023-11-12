from pydantic import model_validator
from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from models.db.user_token import UserToken


class UserTokenEmailChange(UserToken):
    __tablename__ = 'user_token_email_change'

    from_email: Mapped[str] = mapped_column(Unicode, nullable=False)
    to_email: Mapped[str] = mapped_column(Unicode, nullable=False)

    # TODO: SQL
    @model_validator(mode='after')
    def validate_email_change(self) -> None:
        if self.from_email == self.to_email:
            raise ValueError(f'{self.__class__.__qualname__} from and to emails are the same')
