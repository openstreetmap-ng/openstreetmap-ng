from datetime import datetime
from typing import Literal, NewType, NotRequired, TypedDict

from app.models.db.user import UserDisplay, UserId

MailId = NewType('MailId', int)
MailSource = Literal[None, 'message', 'diary_comment']  # None: for system/no source


class MailInit(TypedDict):
    source: MailSource
    from_user_id: UserId | None
    to_user_id: UserId
    subject: str
    body: str
    ref: str | None
    priority: int


class Mail(MailInit):
    id: MailId
    processing_counter: int
    created_at: datetime
    scheduled_at: datetime

    # runtime
    from_user: NotRequired[UserDisplay]
    to_user: NotRequired[UserDisplay]
