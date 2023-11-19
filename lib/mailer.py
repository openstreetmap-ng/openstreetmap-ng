import logging
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate

import anyio
from aiosmtplib import SMTP
from sqlalchemy import null, or_, select
from sqlalchemy.orm import joinedload

from config import (
    SMTP_HOST,
    SMTP_MESSAGES_FROM,
    SMTP_NOREPLY_FROM,
    SMTP_NOREPLY_FROM_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_SECURE,
    SMTP_USER,
)
from db import DB
from lib.translation import render, translation_context
from limits import MAIL_PROCESSING_TIMEOUT, MAIL_UNPROCESSED_EXPIRE, MAIL_UNPROCESSED_EXPONENT
from models.db.mail import Mail
from models.db.user import User
from models.db.user_token_email_reply import UserTokenEmailReply
from models.mail_from_type import MailFromType
from utils import utcnow


def _validate_smtp_config():
    return SMTP_NOREPLY_FROM and SMTP_MESSAGES_FROM


def _validate_secure_port(port):
    if port not in (465, 587):
        raise ValueError('SMTP_SECURE is enabled but SMTP_PORT is not 465 or 587')


def _create_smtp_client(host, port, user, password, secure):
    if secure:
        _validate_secure_port(port)
        use_tls = port == 465
        start_tls = True if port == 587 else None
        return SMTP(host, port, user, password, use_tls=use_tls, start_tls=start_tls)
    else:
        return SMTP(host, port, user, password)


if _validate_smtp_config():
    _SMTP = _create_smtp_client(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SECURE)
else:
    logging.warning('SMTP is not configured, mail delivery is disabled')
    _SMTP = None


async def _send_smtp(mail: Mail) -> None:
    if not mail.to_user:
        logging.info('Discarding mail %r to user %d (not found)', mail.id, mail.to_user_id)
        return

    if mail.from_type != MailFromType.system and not mail.from_user:
        logging.info('Discarding mail %r from user %d (not found)', mail.id, mail.from_user_id)
        return

    message = EmailMessage()

    if mail.from_type == MailFromType.system:
        message['From'] = SMTP_NOREPLY_FROM
    else:
        # reverse mail from/to users because this is a reply token
        from_addr = await UserTokenEmailReply.create_from_addr(mail.to_user_id, mail.source.user_id, mail.source.type)
        message['From'] = formataddr((mail.from_user.display_name, from_addr))

    message['To'] = formataddr((mail.to_user.display_name, mail.to_user.email))
    message['Date'] = formatdate()
    message['Subject'] = mail.subject
    message.set_content(mail.body, subtype='html')

    if mail.ref:
        full_ref = f'<osm-{mail.ref}@{SMTP_NOREPLY_FROM_HOST}>'
        logging.debug('Setting mail %r reference to %r', mail.id, full_ref)
        message['In-Reply-To'] = full_ref
        message['References'] = full_ref
        message['X-Entity-Ref-ID'] = full_ref

    if not _SMTP:
        logging.info('Discarding mail %r (SMTP is not configured)', mail.id)
        return

    logging.debug('Sending mail %r', mail.id)
    await _SMTP.send_message(message)


class Mailer:
    @staticmethod
    async def schedule(
        from_user: User | None,
        from_type: MailFromType,
        to_user: User,
        subject: str,
        template_name: str,
        template_data: dict,
        ref: str | None,
        priority: int,
    ) -> None:
        """
        Schedule a mail for later processing.
        """

        # use destination user's preferred language
        with translation_context(to_user.languages):
            body = render(template_name, **template_data)

        mail = Mail(
            from_user_id=from_user.id if from_user else None,
            from_type=from_type,
            to_user_id=to_user.id,
            subject=subject,
            body=body,
            ref=ref,
            priority=priority,
        )

        async with DB() as session:
            logging.debug('Scheduling mail %r to %d with subject %r', mail.id, to_user.id, subject)
            session.add(mail)

    @staticmethod
    async def process_scheduled() -> None:
        """
        Process next scheduled mail.
        """

        async with DB() as session, session.begin():
            now = utcnow()
            stmt = (
                select(Mail)
                .options(
                    joinedload(Mail.from_user),
                    joinedload(Mail.to_user),
                )
                .where(
                    or_(
                        Mail.processing_at == null(),
                        Mail.processing_at <= now,
                    )
                )
                .order_by(
                    Mail.processing_counter,
                    Mail.priority.desc(),
                    Mail.created_at,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )

            mail = (await session.execute(stmt)).scalar_one_or_none()

            # nothing to do
            if not mail:
                return

            try:
                logging.info('Processing mail %r to %d with subject %r', mail.id, mail.to_user.id, mail.subject)
                with anyio.fail_after(MAIL_PROCESSING_TIMEOUT.total_seconds() - 5):
                    await _send_smtp(mail)
                await session.delete(mail)

            except Exception:
                expires_at = mail.created_at + MAIL_UNPROCESSED_EXPIRE
                processing_at = now + timedelta(minutes=mail.processing_counter**MAIL_UNPROCESSED_EXPONENT)

                if expires_at < processing_at:
                    logging.warning(
                        'Expiring unprocessed mail %r, created at: %r',
                        mail.id,
                        mail.created_at,
                        exc_info=True,
                    )
                    await session.delete(mail)
                    return

                logging.info('Requeuing unprocessed mail %r', mail.id, exc_info=True)
                mail.processing_counter += 1
                mail.processing_at = processing_at
                # TODO: redundant? await session.commit()
