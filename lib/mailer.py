import logging
from abc import ABC
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from smtplib import SMTP
from typing import Sequence

import anyio
from aiosmtplib import SMTP
from cachetools import TTLCache, cached
from jinja2 import Environment, FileSystemLoader
from motor.core import AgnosticClientSession
from pymongo import ASCENDING, DESCENDING

from config import (SMTP_HOST, SMTP_MESSAGES_FROM, SMTP_NOREPLY_FROM,
                    SMTP_NOREPLY_FROM_HOST, SMTP_PASS, SMTP_PORT, SMTP_SECURE,
                    SMTP_USER)
from lib.translation import get_translation
from limits import MAIL_PROCESSING_TIMEOUT
from models.collections.mail import Mail
from models.collections.user import User
from models.collections.user_token_email_reply import UserTokenEmailReply
from models.mail_from import MailSource
from utils import utcnow


def _validate_smtp_config():
    return SMTP_NOREPLY_FROM and SMTP_MESSAGES_FROM


def _validate_secure_port(port):
    if port not in (465, 587):
        raise ValueError('SMTP_SECURE is enabled but SMTP_PORT is not 465 or 587')


def _create_smtp_client(host, port, user, password, secure):
    if secure:
        _validate_secure_port(port)
        use_tls = (port == 465)
        start_tls = True if port == 587 else None
        return SMTP(host, port, user, password, use_tls=use_tls, start_tls=start_tls)
    else:
        return SMTP(host, port, user, password)


if _validate_smtp_config():
    _SMTP = _create_smtp_client(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SECURE)
else:
    logging.warning('SMTP is not configured, mail delivery is disabled')
    _SMTP = None


_J2 = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=True,
    auto_reload=False,
    extensions=['jinja2.ext.i18n'])  # TODO: extension in overlay? test!


@cached(TTLCache(128, ttl=3600))
def _j2(languages: Sequence[str]) -> Environment:
    '''
    Get a Jinja2 environment with translations for the preferred languages.
    '''

    j2 = _J2.overlay()
    j2.install_gettext_translations(get_translation(languages), newstyle=True)
    return j2


async def _send_smtp(mail: 'Mail') -> None:
    message = EmailMessage()

    if not (to_user := await User.find_one_by_id(mail.to_user_id)):
        logging.info('Skipping mail to user %d (not found)', mail.to_user_id)
        return

    if mail.source and (source_user := await User.find_one_by_id(mail.source.user_id)):
        # reverse mail from/to users because this is a reply token
        from_addr = await UserTokenEmailReply.create_from_addr(mail.to_user_id, mail.source.user_id, mail.source.type)
        message['From'] = formataddr((source_user.display_name, from_addr))
    else:
        message['From'] = SMTP_NOREPLY_FROM

    message['To'] = formataddr((to_user.display_name, to_user.email))
    message['Date'] = formatdate()  # TODO: test format UTC
    message['Subject'] = mail.subject
    message.set_content(mail.body, subtype='html')

    if mail.ref:
        full_ref = f'<osm-{mail.ref}@{SMTP_NOREPLY_FROM_HOST}>'
        logging.debug('Setting mail reference to %r', full_ref)
        message['In-Reply-To'] = full_ref
        message['References'] = full_ref
        message['X-Entity-Ref-ID'] = full_ref

    if not _SMTP:
        logging.info('Skipping mail to %r with subject %r (SMTP is not configured)', mail.recipient, mail.subject)
        return

    logging.info('Sending mail to %r with subject %r', mail.recipient, mail.subject)
    await _SMTP.send_message(message)


class Mailer(ABC):
    @staticmethod
    async def schedule(
            cls,
            source: MailSource | None,
            to_user: User,
            subject: str,
            template_name: str,
            template_data: dict,
            ref: str | None,
            priority: int,
            session: AgnosticClientSession | None) -> Mail:
        j2 = _j2(to_user.languages)
        template = j2.get_template(template_name)
        body = template.render(**template_data)
        mail = cls(
            source=source,
            to_user_id=to_user.id,
            subject=subject,
            body=body,
            ref=ref,
            priority=priority)
        await mail.create(session=session)
        return mail

    @staticmethod
    async def process_scheduled() -> Mail | None:
        now = utcnow()
        mail = await Mail.find_and_update(
            {
                '$or': [
                    {'processing_at': None},
                    {'processing_at': {'$lt': now - MAIL_PROCESSING_TIMEOUT}}
                ]
            }, {
                '$set': {'processing_at': now},
                '$inc': {'processing_counter': 1},
            },
            sort={
                'processing_counter': ASCENDING,
                'priority': DESCENDING,
                'created_at': ASCENDING,
            },
            return_after=True)

        if not mail:
            return None

        with anyio.fail_after((mail.processing_at + MAIL_PROCESSING_TIMEOUT - utcnow()).total_seconds() - 5):
            await _send_smtp(mail)

        await mail.delete()
        return mail
