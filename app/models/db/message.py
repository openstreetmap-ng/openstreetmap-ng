import logging
from datetime import datetime
from email.message import EmailMessage, MIMEPart
from typing import NotRequired, TypedDict

import cython
from bs4 import BeautifulSoup
from zid import zid

from app.lib.rich_text import resolve_rich_text
from app.models.db.user import UserDisplay
from app.models.types import MessageId, UserId


class MessageInit(TypedDict):
    id: MessageId
    from_user_id: UserId
    subject: str
    body: str  # TODO: validate size

    # runtime
    to_user_ids: NotRequired[list[UserId]]


class Message(MessageInit):
    from_user_hidden: bool
    body_rich_hash: bytes | None
    created_at: datetime

    # runtime
    from_user: NotRequired[UserDisplay]
    body_rich: NotRequired[str]
    recipients: NotRequired[list['MessageRecipient']]


class MessageRecipient(TypedDict):
    message_id: MessageId
    user_id: UserId
    hidden: bool
    read: bool

    # runtime
    user: NotRequired[UserDisplay]


async def messages_resolve_rich_text(objs: list[Message]) -> None:
    await resolve_rich_text(objs, 'message', 'body', 'markdown')


def message_from_email(
    mail: EmailMessage, from_user_id: UserId, to_user_id: UserId
) -> MessageInit:
    """Create a message instance from an email message."""
    subject: str | None = mail.get('Subject')
    if subject is None:
        raise ValueError('Email message has no subject')

    if mail.is_multipart():
        body = None
        for part in mail.iter_parts():
            body = _get_body(part)
            if body is not None:
                break
    else:
        body = _get_body(mail)

    if body is None:
        raise ValueError(f'Email message {subject!r} has no body')

    message_id: MessageId = zid()  # type: ignore
    message: MessageInit = {
        'id': message_id,
        'from_user_id': from_user_id,
        'to_user_ids': [to_user_id],
        'subject': subject,
        'body': body,  # TODO: body check etc.
    }
    return message


@cython.cfunc
def _get_body(part: MIMEPart):
    content_type: str = part.get_content_type()
    if content_type not in {'text/plain', 'text/html'}:
        return None

    payload_bytes: bytes | None = part.get_payload(decode=True)  # type: ignore
    if payload_bytes is None:
        return None

    logging.debug('Extracted email message body from %r mime part', content_type)
    if content_type == 'text/html':
        return BeautifulSoup(payload_bytes, 'lxml').get_text(separator=' ').strip()
    else:
        return payload_bytes.decode()
