import logging
from asyncio import Lock, TaskGroup, get_running_loop, timeout
from contextlib import asynccontextmanager
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from time import time
from typing import Any, Literal, overload

import cython
from aiosmtplib import SMTP
from psycopg.rows import dict_row
from sentry_sdk import capture_exception
from zid import zid

from app.config import (
    APP_DOMAIN,
    APP_URL,
    ENV,
    MAIL_PROCESSING_TIMEOUT,
    MAIL_UNPROCESSED_EXPIRE,
    MAIL_UNPROCESSED_EXPONENT,
    SMTP_HOST,
    SMTP_NOREPLY_FROM,
    SMTP_NOREPLY_FROM_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
)
from app.db import db
from app.lib.auth_context import auth_context
from app.lib.crypto import hash_bytes
from app.lib.date_utils import utcnow
from app.lib.render_jinja import render_jinja
from app.lib.translation import translation_context
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.mail import Mail, MailInit, MailSource
from app.models.db.user import User, user_is_deleted, user_is_test
from app.models.proto.server_pb2 import StatelessUserTokenStruct
from app.models.types import MailId, UserId
from app.queries.user_query import UserQuery
from app.utils import extend_query_params

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
        with auth_context(to_user), translation_context(to_user['language']):
            body = render_jinja(template_name, template_data)

        mail_id: MailId = zid()  # type: ignore
        mail_init: MailInit = {
            'id': mail_id,
            'source': source,
            'from_user_id': from_user_id,
            'to_user_id': to_user['id'],
            'subject': subject,
            'body': body,
            'ref': ref,
            'priority': priority,
        }

        async with db(True, autocommit=True) as conn:
            await conn.execute(
                """
                INSERT INTO mail (
                    id, source, from_user_id, to_user_id,
                    subject, body, ref, priority
                )
                VALUES (
                    %(id)s, %(source)s, %(from_user_id)s, %(to_user_id)s,
                    %(subject)s, %(body)s, %(ref)s, %(priority)s
                )
                """,
                mail_init,
            )

        logging.info(
            'Scheduled mail %r to user %d with subject %r',
            mail_id,
            to_user['id'],
            subject,
        )

        loop = get_running_loop()
        loop.create_task(_process_task())  # noqa: RUF006


async def _process_task() -> None:
    """Process scheduled mail in the database."""
    if _PROCESS_LOCK.locked():
        return

    async with _PROCESS_LOCK:
        try:
            await _process_task_inner()
        except Exception:
            capture_exception()

    # Avoids race conditions in which scheduled mail is not processed immediately.
    # In rare cases, there will be more than one task running at the time (per process).
    await _process_task_inner()


async def _process_task_inner() -> None:
    logging.debug('Started scheduled mail processing')

    async with _smtp_factory() as smtp, db(True) as conn:
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
                    capture_exception()
                    expires_at = mail['created_at'] + MAIL_UNPROCESSED_EXPIRE
                    scheduled_at = now + timedelta(
                        minutes=mail['processing_counter'] ** MAIL_UNPROCESSED_EXPONENT
                    )

                    if expires_at <= scheduled_at:
                        logging.warning(
                            'Expiring unprocessed mail %r, created at: %r',
                            mail_id,
                            mail['created_at'],
                            exc_info=True,
                        )
                        await conn.execute('DELETE FROM mail WHERE id = %s', (mail_id,))
                        continue

                    logging.info(
                        'Requeuing unprocessed mail %r', mail_id, exc_info=True
                    )
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
    to_user_id = mail['to_user_id']
    from_user_id = mail['from_user_id']

    async with TaskGroup() as tg:
        to_user_task = tg.create_task(UserQuery.find_by_id(to_user_id))
        from_user_task = (
            tg.create_task(UserQuery.find_by_id(from_user_id))
            if from_user_id is not None
            else None
        )

    to_user = to_user_task.result()
    assert to_user is not None, f'Recipient user {to_user_id} not found'
    from_user = from_user_task.result() if from_user_task is not None else None
    assert (from_user is not None) == (from_user_id is not None), (
        f'Sender user {from_user_id} not found'
    )

    if user_is_deleted(to_user):
        logging.info('Discarding mail %r to deleted user %d', mail_id, to_user_id)
        return

    if user_is_test(to_user) and ENV == 'prod':
        logging.info('Discarding mail %r to test user %d', mail_id, to_user_id)
        return

    message = EmailMessage()

    if mail['source'] is None:  # system mail
        message['From'] = SMTP_NOREPLY_FROM

    else:
        # Avoid circular import
        from app.services.user_token_email_reply_service import (  # noqa: PLC0415
            UserTokenEmailReplyService,
        )

        assert from_user is not None, f'Sender must be set for {mail["source"]=!r}'
        reply_address = await UserTokenEmailReplyService.create_address(
            mail_source=mail['source'],
            replying_user=from_user,
            reply_to_user_id=to_user_id,
        )
        message['From'] = formataddr((from_user['display_name'], reply_address))

    message['To'] = formataddr((to_user['display_name'], to_user['email']))
    message['Date'] = formatdate()
    message['Subject'] = mail['subject']
    message.set_content(mail['body'], subtype='html')

    if ref := mail['ref']:
        _set_reference(message, ref)
        _set_list_headers(message, ref, to_user)
        logging.debug('Set mail %r reference to %r', mail_id, ref)

    async with timeout(MAIL_PROCESSING_TIMEOUT.total_seconds() - 5):
        await smtp.send_message(message)

    logging.info(
        'Sent mail %r to user %d with subject %r',
        mail_id,
        mail['to_user_id'],
        mail['subject'],
    )


@cython.cfunc
def _set_reference(message: EmailMessage, ref: str):
    full_ref = f'<osm-{ref}@{SMTP_NOREPLY_FROM_HOST}>'
    message['In-Reply-To'] = full_ref
    message['References'] = full_ref
    message['X-Entity-Ref-ID'] = full_ref  # Disables threading in GMail


@cython.cfunc
def _set_list_headers(message: EmailMessage, ref: str, to_user: User):
    ref_type, ref_id = ref.split('-', 1)
    list_archive = f'{APP_URL}/{ref_type}/{ref_id}'
    list_unsubscribe = f'{APP_URL}/{ref_type}/{ref_id}/unsubscribe'

    if ref_type == 'diary':
        list_title_prefix = 'Diary Entry'
    elif ref_type == 'changeset':
        list_title_prefix = 'Changeset'
    elif ref_type == 'note':
        list_title_prefix = 'Note'
    else:
        logging.warning('Unsupported mail reference type: %r', ref_type)
        return

    # Append stateless token param
    token = UserTokenStructUtils.to_str(
        StatelessUserTokenStruct(
            timestamp=int(time()),
            user_id=to_user['id'],
            email_hashed=hash_bytes(to_user['email']),
            unsubscribe=StatelessUserTokenStruct.UnsubscribeData(
                target=ref_type,
                target_id=int(ref_id),
            ),
        )
    )
    list_unsubscribe = extend_query_params(list_unsubscribe, {'token': token})

    message['List-ID'] = formataddr((
        f'{list_title_prefix} #{ref_id}',
        f'{ref_id}.{ref_type}.{APP_DOMAIN}',
    ))
    message['List-Archive'] = f'<{list_archive}>'
    message['List-Unsubscribe'] = f'<{list_unsubscribe}>'
    message['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'


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
