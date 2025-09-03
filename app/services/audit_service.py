import asyncio
import logging
from asyncio import Event, TaskGroup
from contextlib import asynccontextmanager
from datetime import timedelta
from ipaddress import ip_address
from random import random, uniform
from typing import Literal

import cython
from sentry_sdk.api import start_transaction
from zid import zid

from app.config import (
    AUDIT_RETENTION_ADMIN_TASK,
    AUDIT_RETENTION_AUTH_API,
    AUDIT_RETENTION_AUTH_FAIL,
    AUDIT_RETENTION_AUTH_WEB,
    AUDIT_RETENTION_CHANGE_DISPLAY_NAME,
    AUDIT_RETENTION_CHANGE_EMAIL,
    AUDIT_RETENTION_CHANGE_PASSWORD,
    AUDIT_USER_AGENT_MAX_LENGTH,
    ENV,
)
from app.db import db
from app.lib.auth_context import auth_app, auth_user
from app.lib.retry import retry
from app.lib.sentry import (
    SENTRY_AUDIT_MANAGEMENT_MONITOR,
    SENTRY_AUDIT_MANAGEMENT_MONITOR_SLUG,
)
from app.lib.testmethod import testmethod
from app.middlewares.request_context_middleware import get_request
from app.models.db.audit import AuditEventInit, AuditId, AuditType
from app.models.types import ApplicationId, DisplayName, Email, UserId

_TG: TaskGroup
_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()

_AUDIT_RETENTION: dict[AuditType, timedelta] = {
    'admin_task': AUDIT_RETENTION_ADMIN_TASK,
    'auth_api': AUDIT_RETENTION_AUTH_API,
    'auth_fail': AUDIT_RETENTION_AUTH_FAIL,
    'auth_web': AUDIT_RETENTION_AUTH_WEB,
    'change_display_name': AUDIT_RETENTION_CHANGE_DISPLAY_NAME,
    'change_email': AUDIT_RETENTION_CHANGE_EMAIL,
    'change_password': AUDIT_RETENTION_CHANGE_PASSWORD,
}


class AuditService:
    @staticmethod
    @asynccontextmanager
    async def context():
        global _TG
        async with (_TG := TaskGroup()):  # pyright: ignore[reportConstantRedefinition]
            task = _TG.create_task(_process_task())
            yield
            task.cancel()  # avoid "Task was destroyed" warning during tests

    @staticmethod
    @testmethod
    async def force_process():
        """
        Force the audit processing loop to wake up early, and wait for it to finish.
        This method is only available during testing, and is limited to the current process.
        """
        logging.debug('Requesting audit processing loop early wakeup')
        _PROCESS_REQUEST_EVENT.set()
        _PROCESS_DONE_EVENT.clear()
        await _PROCESS_DONE_EVENT.wait()


def audit(
    type: AuditType,
    /,
    *,
    # Event metadata
    user_id: UserId | None | Literal['UNSET'] = 'UNSET',
    application_id: ApplicationId | None | Literal['UNSET'] = 'UNSET',
    email: Email | None = None,
    display_name: DisplayName | None = None,
    extra: str | None = None,
    # Event config
    sample_rate: float = 1,
    discard_repeated: timedelta | None = None,
    # Constants
    AUDIT_USER_AGENT_MAX_LENGTH: cython.Py_ssize_t = AUDIT_USER_AGENT_MAX_LENGTH,
) -> None:
    if sample_rate < 1 and random() > sample_rate:
        return

    if user_id == 'UNSET':
        user = auth_user()
        user_id = user['id'] if user is not None else None

    assert discard_repeated is None or user_id is not None, (
        'discard_repeated requires user_id to be set'
    )

    if application_id == 'UNSET':
        application_id = auth_app()

    req = get_request()
    req_ip = ip_address(req.client.host)  # type: ignore
    req_ua = req.headers.get('User-Agent')

    event_id: AuditId = zid()  # type: ignore
    event_init: AuditEventInit = {
        'id': event_id,
        'type': type,
        'ip': req_ip,
        'user_agent': (
            req_ua[:AUDIT_USER_AGENT_MAX_LENGTH]  #
            if req_ua is not None
            else None
        ),
        'user_id': user_id,
        'application_id': application_id,
        'email': email,
        'display_name': display_name,
        'extra': extra,
    }

    _TG.create_task(_audit_task(event_init, discard_repeated))

    # Skip logging for common cases
    if type in {'auth_api', 'auth_web'} and extra is None:
        return

    values: list[str] = []
    if user_id is not None:
        values.append(f'uid={user_id}')
    if application_id is not None:
        values.append(f'aid={application_id}')
    if email is not None:
        values.append(f'{email=}')
    if display_name is not None:
        values.append(f'{display_name=}')

    logging.info(
        'AUDIT: %s %s "%s": %s [%s]',
        req_ip,
        type,
        ' '.join(values),
        extra,
        event_id,
    )


async def _audit_task(
    event_init: AuditEventInit,
    discard_repeated: timedelta | None,
) -> None:
    async with (
        db(True) as conn,
        await conn.execute(
            """
            INSERT INTO audit (
                id, type,
                ip, user_agent, user_id, application_id,
                email, display_name, extra
            )
            SELECT
                %(id)s, %(type)s,
                %(ip)s, %(user_agent)s, %(user_id)s, %(application_id)s,
                %(email)s, %(display_name)s, %(extra)s
            WHERE NOT EXISTS (
                SELECT 1 FROM audit
                WHERE %(discard_repeated)s IS NOT NULL
                AND user_id = %(user_id)s
                AND type = %(type)s
                AND created_at > (statement_timestamp() - %(discard_repeated)s)
                LIMIT 1
            )
            """,
            {**event_init, 'discard_repeated': discard_repeated},
        ) as cursor,
    ):
        if not cursor.rowcount:
            logging.debug('Discarded repeated audit event %s', event_init['id'])


@retry(None)
async def _process_task() -> None:
    async def sleep(delay: float) -> None:
        if ENV != 'dev':
            await asyncio.sleep(delay)
            return

        # Dev environment supports early wakeup
        _PROCESS_DONE_EVENT.set()
        async with TaskGroup() as tg:
            event_task = tg.create_task(_PROCESS_REQUEST_EVENT.wait())
            await asyncio.wait((event_task,), timeout=delay)
            if event_task.done():
                logging.debug('Audit processing loop early wakeup')
                _PROCESS_REQUEST_EVENT.clear()
            else:
                event_task.cancel()

    while True:
        async with db(True) as conn:
            # Lock is just a random unique number
            async with await conn.execute(
                'SELECT pg_try_advisory_xact_lock(3968087525058357795::bigint)'
            ) as r:
                acquired: bool = (await r.fetchone())[0]  # type: ignore

            if acquired:
                with (
                    SENTRY_AUDIT_MANAGEMENT_MONITOR,
                    start_transaction(
                        op='task', name=SENTRY_AUDIT_MANAGEMENT_MONITOR_SLUG
                    ),
                ):
                    await _cleanup_old_audit_logs()

                # on success, sleep 5min (handle burst)
                await sleep(300)

        # on success/failure, sleep ~24h
        await sleep(uniform(23.5 * 3600, 24.5 * 3600))


async def _cleanup_old_audit_logs() -> None:
    """Delete old audit logs based on configured retention periods."""
    async with db(True) as conn:
        for audit_type, retention in _AUDIT_RETENTION.items():
            result = await conn.execute(
                """
                DELETE FROM audit
                WHERE type = %s
                AND created_at < statement_timestamp() - %s
                """,
                (audit_type, retention),
            )

            if result.rowcount:
                logging.debug(
                    'Deleted %d old %r audit logs', result.rowcount, audit_type
                )
