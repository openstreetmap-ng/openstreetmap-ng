import logging
from asyncio import Lock, TaskGroup, get_running_loop, timeout
from contextlib import asynccontextmanager
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from typing import Any, Literal, overload

import cython
from aiosmtplib import SMTP
from arrow.api import utcnow
from psycopg.rows import dict_row

from app.config import (
    SMTP_HOST,
    SMTP_NOREPLY_FROM,
    SMTP_NOREPLY_FROM_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
    TEST_ENV,
)
from app.db import db2
from app.lib.auth_context import auth_context
from app.lib.render_jinja import render_jinja
from app.lib.translation import translation_context
from app.limits import MAIL_PROCESSING_TIMEOUT, MAIL_UNPROCESSED_EXPIRE, MAIL_UNPROCESSED_EXPONENT
from app.models.db.mail import Mail, MailInit, MailSource
from app.models.db.user import User, user_is_deleted, user_is_test
from app.models.types import UserId

_PROCESS_LOCK = Lock()


class EmailService:
    @staticmethod
    @asynccontextmanager
    async def context():
        """Context manager for email service."""
        async with TaskGroup() as tg:
            task = tg.create_task(_process_task())
            yield
            task.cancel()  # avoid "Task was destroyed" warning during tests

    @staticmethod
    @overload
    async def schedule(
        source: None,
        from_user_id: None,
        to_user: User,
        subject: str,
        template_name: str,
        template_data: dict[str, Any],
        ref: str | None = None,
        priority: int = 0,
    ) -> None: ...
    @staticmethod
    @overload
    async def schedule(
        source: Literal['message', 'diary_comment'],
        from_user_id: UserId,
        to_user: User,
        subject: str,
        template_name: str,
        template_data: dict[str, Any],
        ref: str | None = None,
        priority: int = 0,
    ) -> None: ...
    @staticmethod
    async def schedule(
        source: MailSource,
        from_user_id: UserId | None,
        to_user: User,
        subject: str,
        template_name: str,
        template_data: dict[str, Any],
        ref: str | None = None,
        priority: int = 0,
    ) -> None:
        """Schedule mail and start async processing."""
        # render in the to_user's language
        with auth_context(to_user, ()), translation_context(to_user['language']):
            body = render_jinja(template_name, template_data)

        mail_init: MailInit = {
            'source': source,
            'from_user_id': from_user_id,
            'to_user_id': to_user['id'],
            'subject': subject,
            'body': body,
            'ref': ref,
            'priority': priority,
        }

        async with (
            db2(True, autocommit=True) as conn,
            await conn.execute(
                """
                INSERT INTO mail (
                    source, from_user_id, to_user_id, subject, body, ref, priority
                )
                VALUES (
                    %(source)s, %(from_user_id)s, %(to_user_id)s, %(subject)s, %(body)s, %(ref)s, %(priority)s
                )
                RETURNING id
                """,
                mail_init,
            ) as r,
        ):
            row = await r.fetchone()
            assert row is not None, 'Mail must be scheduled'
            logging.info('Scheduled mail %r to user %d with subject %r', row[0], to_user['id'], subject)

        loop = get_running_loop()
        loop.create_task(_process_task())  # noqa: RUF006


async def _process_task() -> None:
    """Process scheduled mail in the database."""
    if _PROCESS_LOCK.locked():
        return

    async with _PROCESS_LOCK:
        try:
            await _process_task_inner()
        except Exception:  # noqa: S110
            pass

    # Avoids race conditions in which scheduled mail is not processed immediately.
    # In rare cases, there will be more than one task running at the time (per process).
    await _process_task_inner()


async def _process_task_inner() -> None:
    logging.debug('Started scheduled mail processing')

    async with _smtp_factory() as smtp, db2(True) as conn:
        while True:
            now = utcnow()
            async with await conn.cursor(row_factory=dict_row).execute(
                """
                SELECT * FROM mail
                WHERE scheduled_at <= %s
                ORDER BY processing_counter, priority DESC, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (now,),
            ) as r:
                mail: Mail | None = await r.fetchone()  # type: ignore
                if mail is None:
                    logging.debug('Finished scheduled mail processing')
                    break

                mail_id = mail['id']
                # TODO: Use UserQuery to load user data for from_user_id and to_user_id

                try:
                    logging.debug('Processing mail %r', mail_id)
                    await _send_mail(smtp, mail)
                    await conn.execute('DELETE FROM mail WHERE id = %s', (mail_id,))

                except Exception:
                    expires_at = mail['created_at'] + MAIL_UNPROCESSED_EXPIRE
                    scheduled_at = now + timedelta(minutes=mail['processing_counter'] ** MAIL_UNPROCESSED_EXPONENT)

                    if expires_at <= scheduled_at:
                        logging.warning(
                            'Expiring unprocessed mail %r, created at: %r',
                            mail_id,
                            mail['created_at'],
                            exc_info=True,
                        )
                        await conn.execute('DELETE FROM mail WHERE id = %s', (mail_id,))
                        continue

                    logging.info('Requeuing unprocessed mail %r', mail_id, exc_info=True)
                    await conn.execute(
                        """
                        UPDATE mail
                        SET
                            processing_counter = processing_counter + 1,
                            scheduled_at = %(scheduled_at)s
                        WHERE id = %(id)s
                        """,
                        {
                            'id': mail_id,
                            'scheduled_at': scheduled_at,
                        },
                    )


async def _send_mail(smtp: SMTP, mail: Mail) -> None:
    mail_id = mail['id']
    to_user = mail['to_user']  # pyright: ignore [reportTypedDictNotRequiredAccess]

    if user_is_deleted(to_user):
        logging.info('Discarding mail %r to deleted user %d', mail_id, mail['to_user_id'])
        return

    if user_is_test(to_user) and not TEST_ENV:
        logging.info('Discarding mail %r to test user %d', mail_id, mail['to_user_id'])
        return

    message = EmailMessage()

    if mail['source'] is None:  # system mail
        message['From'] = SMTP_NOREPLY_FROM

    else:
        from app.services.user_token_email_reply_service import UserTokenEmailReplyService  # noqa: PLC0415

        from_user = mail['from_user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
        reply_address = await UserTokenEmailReplyService.create_address(to_user, mail['source'])
        message['From'] = formataddr((from_user['display_name'], reply_address))

    message['To'] = formataddr((to_user['display_name'], to_user['email']))
    message['Date'] = formatdate()
    message['Subject'] = mail['subject']
    message.set_content(mail['body'], subtype='html')

    if mail['ref']:
        full_ref = f'<osm-{mail["ref"]}@{SMTP_NOREPLY_FROM_HOST}>'
        logging.debug('Setting mail %r reference to %r', mail_id, full_ref)
        message['In-Reply-To'] = full_ref
        message['References'] = full_ref
        message['X-Entity-Ref-ID'] = full_ref  # disables threading in gmail

    async with timeout(MAIL_PROCESSING_TIMEOUT.total_seconds() - 5):
        await smtp.send_message(message)

    logging.info('Sent mail %r to user %d with subject %r', mail_id, mail['to_user_id'], mail['subject'])


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
