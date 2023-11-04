from datetime import datetime
from typing import Annotated

from pydantic import Field, NonNegativeInt

from limits import MAIL_UNPROCESSED_EXPIRE
from models.collections.base_sequential import BaseSequential, SequentialId
from models.mail_from import MailSource
from models.str import NonEmptyStr
from utils import utcnow


class Mail(BaseSequential):
    source: Annotated[MailSource | None, Field(frozen=True)]
    to_user_id: Annotated[SequentialId, Field(frozen=True)]
    subject: Annotated[NonEmptyStr, Field(frozen=True)]
    body: Annotated[NonEmptyStr, Field(frozen=True)]
    ref: Annotated[NonEmptyStr | None, Field(frozen=True)]
    priority: Annotated[int, Field(frozen=True)]

    # defaults
    created_at: Annotated[datetime, Field(frozen=True, default_factory=utcnow)]
    expires_at: Annotated[datetime, Field(frozen=True, default_factory=lambda: utcnow() + MAIL_UNPROCESSED_EXPIRE)]
    processing_at: datetime | None = None
    processing_counter: NonNegativeInt = 0
