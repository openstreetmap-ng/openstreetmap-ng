import logging
from datetime import datetime
from email.message import EmailMessage, MIMEPart
from typing import NotRequired, TypedDict

import cython
from lxml import html as lxml_html
from lxml.etree import ParserError
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
    user_recipient: NotRequired['MessageRecipient']


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

    body = _get_message_body(mail)
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
def _get_message_body(mail: EmailMessage) -> str | None:
    html_part: MIMEPart | None = None

    for part in mail.walk():
        if part.is_multipart():
            continue
        if part.get_content_disposition() == 'attachment':
            continue

        content_type = part.get_content_type()

        if content_type == 'text/plain':
            payload: bytes | None = part.get_payload(decode=True)  # type: ignore
            if payload is None:
                continue

            text = _decode_payload(payload, part.get_content_charset())
            if text.strip():
                logging.debug('Extracted email message body from text')
                return text

        elif content_type == 'text/html':
            html_part = part

    if html_part is None:
        return None

    payload: bytes | None = html_part.get_payload(decode=True)  # type: ignore
    if payload is None:
        return None

    html = _decode_payload(payload, html_part.get_content_charset())
    text = _html_to_text(html)
    if text.strip():
        logging.debug('Extracted email message body from HTML')
        return text

    return None


@cython.cfunc
def _decode_payload(payload: bytes, charset: str | None) -> str:
    if charset is not None:
        try:
            return payload.decode(charset)
        except (LookupError, UnicodeDecodeError):
            pass

    try:
        return payload.decode()
    except UnicodeDecodeError:
        return payload.decode('latin-1', errors='replace')


@cython.cfunc
def _html_to_text(html: str) -> str:
    try:
        document = lxml_html.document_fromstring(html)
    except (ParserError, ValueError):
        return ''

    body = document.find('body')
    root = body if body is not None else document
    for el in list(root.iter('script', 'style')):
        el.drop_tree()

    return ' '.join(root.itertext()).strip()
