import logging
from asyncio import TaskGroup
from contextlib import asynccontextmanager
from datetime import timedelta
from ipaddress import ip_address
from random import random

import cython
from zid import zid

from app.config import AUDIT_USER_AGENT_MAX_LENGTH
from app.db import db
from app.lib.auth_context import auth_user
from app.middlewares.request_context_middleware import get_request
from app.models.db.audit import AuditEventInit, AuditId, AuditType
from app.models.types import ApplicationId, DisplayName, Email, UserId

_TG: TaskGroup


@asynccontextmanager
async def audit_context():
    global _TG
    async with (_TG := TaskGroup()):  # pyright: ignore[reportConstantRedefinition]
        yield


def audit(
    type: AuditType,
    /,
    *,
    # Event metadata
    user_id: UserId | None = None,
    application_id: ApplicationId | None = None,
    email: Email | None = None,
    display_name: DisplayName | None = None,
    extra: str | None = None,
    # Event config
    sample_rate: float | None = None,
    discard_repeated: timedelta | None = None,
    # Constants
    AUDIT_USER_AGENT_MAX_LENGTH: cython.Py_ssize_t = AUDIT_USER_AGENT_MAX_LENGTH,
) -> None:
    if sample_rate is not None and random() > sample_rate:
        return

    if user_id is None:
        user = auth_user()
        user_id = user['id'] if user is not None else None
    assert discard_repeated is None or user_id is not None, (
        'discard_repeated requires user_id to be set'
    )

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
                email, display_name,
                extra
            )
            SELECT
                %(id)s, %(type)s,
                %(ip)s, %(user_agent)s, %(user_id)s, %(application_id)s,
                %(email)s, %(display_name)s,
                %(extra)s
            WHERE NOT EXISTS (
                SELECT 1 FROM audit
                WHERE %(discard_repeated)s IS NOT NULL
                AND user_id = %(user_id)s
                AND type = %(type)s
                AND created_at > statement_timestamp() - %(discard_repeated)s
                LIMIT 1
            )
            """,
            {**event_init, 'discard_repeated': discard_repeated},
        ) as cursor,
    ):
        if not cursor.rowcount:
            logging.debug('Discarded repeated audit event %s', event_init['id'])
