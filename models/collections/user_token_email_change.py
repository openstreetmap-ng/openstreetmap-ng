from typing import Annotated

from pydantic import Field, model_validator

from models.collections.user_token import UserToken
from models.str import EmailStr


# TODO: both classes necessary?
class UserTokenEmailChange(UserToken):
    from_email: Annotated[EmailStr, Field(frozen=True)]
    to_email: Annotated[EmailStr, Field(frozen=True)]

    @model_validator(mode='after')
    def validate_email_change(self) -> None:
        if self.from_email == self.to_email:
            raise ValueError(f'{self.__class__.__qualname__} from and to emails are the same')
