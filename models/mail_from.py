from typing import Annotated

from pydantic import BaseModel, Field

from models.collections.base_sequential import SequentialId
from models.mail_from_type import MailSourceType


class MailSource(BaseModel):
    user_id = Annotated[SequentialId, Field(frozen=True)]
    type: Annotated[MailSourceType, Field(frozen=True)]
