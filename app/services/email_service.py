import logging
from asyncio import Lock, get_running_loop, timeout
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from typing import Any

import cython
from aiosmtplib import SMTP
from sqlalchemy import null, or_, select
from sqlalchemy.orm import joinedload

from app.config import (
    SMTP_HOST,
    SMTP_NOREPLY_FROM,
    SMTP_NOREPLY_FROM_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
)
from app.db import db, db_commit
from app.lib.auth_context import auth_context
from app.lib.date_utils import utcnow
from app.lib.jinja_env import render
from app.lib.translation import translation_context
from app.limits import MAIL_PROCESSING_TIMEOUT, MAIL_UNPROCESSED_EXPIRE, MAIL_UNPROCESSED_EXPONENT
from app.models.db.mail import Mail, MailSource
from app.models.db.user import User
from app.services.user_token_email_reply_service import UserTokenEmailReplyService

_process_lock = Lock()


class EmailService:
    @asynccontextmanager
    @staticmethod
    async def context():
        """
        Context manager for email service.
        """
        loop = get_running_loop()
        task = loop.create_task(_process_task())
        yield
        task.cancel()  # avoid "Task was destroyed" warning during tests

    @staticmethod
    async def schedule(
        source: MailSource,
        from_user: User | None,
        to_user: User,
        subject: str,
        template_name: str,
        template_data: dict[str, Any],
        ref: str | None = None,
        priority: int = 0,
    ) -> None:
        """
        Schedule mail and start async processing.
        """
        # render in the to_user's language
        with auth_context(to_user, ()), translation_context(to_user.language):
            body = render(template_name, template_data)

        async with db_commit() as session:
            mail = Mail(
                source=source,
                from_user_id=from_user.id if (from_user is not None) else None,
                to_user_id=to_user.id,
                subject=subject,
                body=body,
                ref=ref,
                priority=priority,
            )
            logging.info('Scheduling mail %r to user %d with subject %r', mail.id, to_user.id, subject)
            session.add(mail)

        loop = get_running_loop()
        loop.create_task(_process_task())  # noqa: RUF006


async def _process_task() -> None:
    """
    Process scheduled mail in the database.
    """
    if _process_lock.locked():
        return
    async with _process_lock:
        with suppress(Exception):
            await _process_task_inner()

    # avoids race conditions in which scheduled mail is not processed immediately
    # in rare cases, there will be more than one task running at the time (per process)
    await _process_task_inner()


async def _process_task_inner() -> None:
    logging.debug('Started scheduled mail processing')

    async with _smtp_factory() as smtp, db() as session:
        while True:
            now = utcnow()
            stmt = (
                select(Mail)
                .options(
                    joinedload(Mail.from_user).load_only(User.display_name),
                    joinedload(Mail.to_user).load_only(User.display_name, User.email),
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
                .with_for_update(of=Mail, skip_locked=True)
                .limit(1)
            )

            mail = await session.scalar(stmt)
            if mail is None:
                logging.debug('Finished scheduled mail processing')
                break

            try:
                logging.debug('Processing mail %r', mail.id)
                await _send_mail(smtp, mail)
                await session.delete(mail)
            except Exception:
                expires_at = mail.created_at + MAIL_UNPROCESSED_EXPIRE
                processing_at = now + timedelta(minutes=mail.processing_counter**MAIL_UNPROCESSED_EXPONENT)

                if expires_at <= processing_at:
                    logging.warning(
                        'Expiring unprocessed mail %r, created at: %r',
                        mail.id,
                        mail.created_at,
                        exc_info=True,
                    )
                    await session.delete(mail)
                else:
                    logging.info('Requeuing unprocessed mail %r', mail.id, exc_info=True)
                    mail.processing_counter += 1
                    mail.processing_at = processing_at
            finally:
                await session.commit()


async def _send_mail(smtp: SMTP, mail: Mail) -> None:
    # TODO: deleted users
    # if not mail.to_user:
    #     logging.info('Discarding mail %r to user %d (not found)', mail.id, mail.to_user_id)
    #     return

    message = EmailMessage()

    if mail.source == MailSource.system:
        message['From'] = SMTP_NOREPLY_FROM
    else:
        from_user = mail.from_user
        if from_user is None:
            raise AssertionError('Mail from user must be set')
        reply_address = await UserTokenEmailReplyService.create_address(
            replying_user=mail.to_user,
            mail_source=mail.source,
        )
        message['From'] = formataddr((from_user.display_name, reply_address))

    message['To'] = formataddr((mail.to_user.display_name, mail.to_user.email))
    message['Date'] = formatdate()
    message['Subject'] = mail.subject
    message.set_content(mail.body, subtype='html')

    if mail.ref:
        full_ref = f'<osm-{mail.ref}@{SMTP_NOREPLY_FROM_HOST}>'
        logging.debug('Setting mail %r reference to %r', mail.id, full_ref)
        message['In-Reply-To'] = full_ref
        message['References'] = full_ref
        message['X-Entity-Ref-ID'] = full_ref  # disables threading in gmail

    async with timeout(MAIL_PROCESSING_TIMEOUT.total_seconds() - 5):
        await smtp.send_message(message)

    logging.info('Sent mail %r to user %d with subject %r', mail.id, mail.to_user_id, mail.subject)


@cython.cfunc
def _smtp_factory():
    port = SMTP_PORT
    use_tls = port == 465
    start_tls = True if port == 587 else None
    return SMTP(
        hostname=SMTP_HOST,
        port=port,
        username=SMTP_USER,
        password=SMTP_PASS,
        use_tls=use_tls,
        start_tls=start_tls,
    )
