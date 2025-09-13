import asyncio
import logging
from asyncio import Event, TaskGroup
from collections.abc import Coroutine
from contextlib import asynccontextmanager, nullcontext
from datetime import timedelta
from ipaddress import ip_address
from random import random, uniform
from typing import Any, Literal

import cython
from psycopg import AsyncConnection
from psycopg.sql import SQL
from psycopg.types.json import Jsonb
from sentry_sdk.api import start_transaction

from app.config import AUDIT_POLICY, AUDIT_USER_AGENT_MAX_LENGTH, ENV
from app.db import db
from app.lib.anonymizer import anonymize_ip
from app.lib.auth_context import auth_app, auth_user
from app.lib.retry import retry
from app.lib.sentry import (
    SENTRY_AUDIT_MANAGEMENT_MONITOR,
    SENTRY_AUDIT_MANAGEMENT_MONITOR_SLUG,
)
from app.lib.testmethod import testmethod
from app.middlewares.request_context_middleware import get_request
from app.models.db.audit import AUDIT_TYPE_VALUES, AuditEventInit, AuditType
from app.models.types import ApplicationId, UserId

_TG: TaskGroup
_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()


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
    conn: AsyncConnection | None = None,
    /,
    *,
    # Event metadata
    user_id: UserId | None | Literal['UNSET'] = 'UNSET',
    target_user_id: UserId | None = None,
    application_id: ApplicationId | None | Literal['UNSET'] = 'UNSET',
    extra: dict[str, Any] | None = None,
    # Event config overrides
    sample_rate: float | None = None,
    discard_repeated: timedelta | None | Literal['UNSET'] = 'UNSET',
    # Constants
    AUDIT_USER_AGENT_MAX_LENGTH: cython.Py_ssize_t = AUDIT_USER_AGENT_MAX_LENGTH,
) -> Coroutine[None, None, None]:
    """
    Log audit events for security monitoring and compliance.
    Schedules the DB write immediately and returns an awaitable.
    """
    audit_policy = AUDIT_POLICY[type]

    if sample_rate is None:
        sample_rate = audit_policy.sample_rate
    if sample_rate < 1 and random() > sample_rate:

        async def _noop():
            return None

        return _noop()

    if user_id == 'UNSET':
        user = auth_user()
        user_id = user['id'] if user is not None else None
    if discard_repeated == 'UNSET':
        discard_repeated = audit_policy.discard_repeated

    assert target_user_id is None or user_id is not None, (
        'target_user_id requires user_id to be set'
    )

    # Simplify current user targeting himself
    if target_user_id is not None and target_user_id == user_id:
        target_user_id = None

    if application_id == 'UNSET':
        application_id = auth_app()

    req = get_request()
    req_ip = ip_address(req.client.host)  # type: ignore
    req_ua = req.headers.get('User-Agent')

    if ENV == 'test':
        req_ip = anonymize_ip(req_ip)

    event_init: AuditEventInit = {
        'type': type,
        'ip': req_ip,
        'user_agent': (
            req_ua[:AUDIT_USER_AGENT_MAX_LENGTH]  #
            if req_ua is not None
            else None
        ),
        'user_id': user_id,
        'target_user_id': target_user_id,
        'application_id': application_id,
        'extra': extra,
    }

    task = _TG.create_task(_audit_task(conn, event_init, discard_repeated))

    if type not in {'auth_api', 'auth_web'} or extra is not None:
        values: list[str] = []
        if user_id is not None:
            values.append(f'uid={user_id}')
        if target_user_id is not None:
            values.append(f'->uid={target_user_id}')
        if application_id is not None:
            values.append(f'aid={application_id}')
        logging.info('AUDIT: %s %s "%s": %s', req_ip, type, ' '.join(values), extra)

    async def _waiter():
        await task

    return _waiter()


async def _audit_task(
    conn: AsyncConnection | None,
    event_init: AuditEventInit,
    discard_repeated: timedelta | None,
) -> None:
    query = SQL("""
        INSERT INTO audit (
            type, ip, user_agent, user_id,
            target_user_id, application_id, extra
        )
        SELECT
            %(type)s, %(ip)s, %(user_agent)s, %(user_id)s,
            %(target_user_id)s, %(application_id)s, %(extra)s
        {}
    """).format(
        SQL(
            """
            WHERE NOT EXISTS (
                SELECT 1 FROM audit
                WHERE type = %(type)s
                AND ip = %(ip)s
                AND user_id IS NOT DISTINCT FROM %(user_id)s
                AND target_user_id IS NOT DISTINCT FROM %(target_user_id)s
                AND application_id IS NOT DISTINCT FROM %(application_id)s
                AND hashtext(extra::text) IS NOT DISTINCT FROM hashtext(%(extra)s::text)
                AND extra::jsonb IS NOT DISTINCT FROM %(extra)s::jsonb
                AND created_at > statement_timestamp() - %(discard_repeated)s
                LIMIT 1
            )
            """
            if discard_repeated is not None
            else ''
        )
    )

    async with nullcontext(conn) if conn is not None else db(True) as conn:  # noqa: PLR1704
        await conn.execute(
            query,
            {
                **event_init,
                'extra': (
                    Jsonb(extra)
                    if (extra := event_init.get('extra')) is not None
                    else None
                ),
                'discard_repeated': discard_repeated,
            },
        )


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
        for audit_type in AUDIT_TYPE_VALUES:
            audit_policy = AUDIT_POLICY[audit_type]
            result = await conn.execute(
                """
                DELETE FROM audit
                WHERE type = %s
                AND created_at < statement_timestamp() - %s
                """,
                (audit_type, audit_policy.retention),
            )

            if result.rowcount:
                logging.debug(
                    'Deleted %d old %r audit logs', result.rowcount, audit_type
                )
