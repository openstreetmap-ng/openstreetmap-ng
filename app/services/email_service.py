import logging
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate

import cython
from aiosmtplib import SMTP
from anyio import CancelScope, Lock, WouldBlock, create_task_group, fail_after
from anyio.abc import TaskGroup
from sqlalchemy import null, or_, select

from app.config import (
    APP_URL,
    SMTP_HOST,
    SMTP_NOREPLY_FROM,
    SMTP_NOREPLY_FROM_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
)
from app.db import db, db_commit
from app.lib.date_utils import utcnow
from app.lib.jinja_env import render
from app.lib.translation import primary_translation_language, translation_context
from app.limits import MAIL_PROCESSING_TIMEOUT, MAIL_UNPROCESSED_EXPIRE, MAIL_UNPROCESSED_EXPONENT
from app.models.db.mail import Mail
from app.models.db.user import User
from app.models.mail_source import MailSource
from app.services.user_token_email_reply_service import UserTokenEmailReplyService

_tg: TaskGroup | None = None
_process_lock = Lock()


class EmailService:
    async def __aenter__(self):
        global _tg
        if _tg is not None:
            raise RuntimeError(f'{self.__aenter__.__qualname__} was reused')
        _tg = create_task_group()
        await _tg.__aenter__()
        _tg.start_soon(_process_task)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        _tg.cancel_scope.cancel()
        await _tg.__aexit__(exc_type, exc, tb)

    @staticmethod
    async def schedule(
        source: MailSource,
        from_user: User | None,
        to_user: User,
        subject: str,
        template_name: str,
        template_data: dict,
        ref: str | None = None,
        priority: int = 0,
    ) -> None:
        """
        Schedule a mail and start async processing.
        """

        # render in the to_user's language
        with translation_context(to_user.language):
            body = render(
                template_name,
                **{
                    'APP_URL': APP_URL,
                    'lang': primary_translation_language(),
                    'user': to_user,
                    **template_data,
                },
            )

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

        _tg.start_soon(_process_task)


async def _process_task() -> None:
    """
    Process scheduled mail in the database.

    In rare cases, there will be more than one task running at the time (per process).
    """

    try:
        _process_lock.acquire_nowait()
        await _process_task_inner()
    except WouldBlock:
        return
    finally:
        _process_lock.release()

    # avoids race conditions in which scheduled mail is not processed immediately
    await _process_task_inner()


async def _process_task_inner() -> None:
    logging.debug('Started scheduled mail processing')

    async with _smtp_factory() as smtp, db() as session:
        while True:
            now = utcnow()
            stmt = (
                select(Mail)
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

                with CancelScope(shield=True):
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
        reply_address = await UserTokenEmailReplyService.create_address(
            replying_user_id=mail.to_user_id,
            mail_source=mail.source,
        )
        message['From'] = formataddr((mail.from_user.display_name, reply_address))

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

    with fail_after(MAIL_PROCESSING_TIMEOUT.total_seconds() - 5):
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
        password=SMTP_PASS.get_secret_value(),
        use_tls=use_tls,
        start_tls=start_tls,
    )
