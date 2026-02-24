import logging
from asyncio import TaskGroup
from contextlib import asynccontextmanager
from datetime import timedelta
from ipaddress import ip_address
from random import random
from typing import Any, Literal

import cython
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message
from psycopg import AsyncConnection
from psycopg.sql import SQL
from psycopg.types.json import Jsonb
from zid import zid

from app.config import (
    AUDIT_CLEANUP_PROBABILITY,
    AUDIT_POLICY,
    AUDIT_USER_AGENT_MAX_LENGTH,
    ENV,
)
from app.db import db
from app.lib.auth_context import auth_oauth2, auth_user
from app.lib.ip import anonymize_ip
from app.middlewares.request_context_middleware import (
    get_request,
    get_request_audit_tasks,
)
from app.models.db.audit import AUDIT_TYPE_VALUES, AuditEventInit
from app.models.proto.audit_types import Type
from app.models.types import ApplicationId, OAuth2TokenId, UserId

_TG: TaskGroup


class AuditService:
    @staticmethod
    @asynccontextmanager
    async def context():
        global _TG
        async with (_TG := TaskGroup()):  # pyright: ignore[reportConstantRedefinition]
            yield


def audit(
    type: Type,
    conn: AsyncConnection | None = None,
    /,
    *,
    # Event metadata
    user_id: UserId | None | Literal['UNSET'] = 'UNSET',
    target_user_id: UserId | None = None,
    oauth2: tuple[ApplicationId, OAuth2TokenId] | None | Literal['UNSET'] = 'UNSET',
    extra_proto: Message | None = None,
    extra: dict[str, Any] | None = None,
    # Event config overrides
    sample_rate: float | None = None,
    discard_repeated: timedelta | None | Literal['UNSET'] = 'UNSET',
    # Constants
    AUDIT_USER_AGENT_MAX_LENGTH: cython.size_t = AUDIT_USER_AGENT_MAX_LENGTH,
):
    """
    Log audit events for security monitoring and compliance.
    Schedules the DB write immediately and returns an awaitable.
    """

    async def _noop():
        return None

    audit_policy = AUDIT_POLICY[type]

    if sample_rate is None:
        sample_rate = audit_policy.sample_rate
    if sample_rate < 1 and random() > sample_rate:
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

    try:
        req = get_request()
    except LookupError:
        logging.info('Audit event %r skipped, missing request context', type)
        return _noop()

    if oauth2 == 'UNSET':
        oauth2 = auth_oauth2()
    application_id, token_id = oauth2 if oauth2 is not None else (None, None)

    req_ip = ip_address(req.client.host)  # type: ignore
    req_ua = req.headers.get('User-Agent')

    if ENV == 'test':
        req_ip = anonymize_ip(req_ip)

    if extra_proto is not None:
        merged_extra = _proto_dict(extra_proto)
        if extra is not None:
            merged_extra.update(extra)
        extra = merged_extra

    event_init: AuditEventInit = {
        'id': zid(),  # type: ignore
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
        'token_id': token_id,
        'extra': extra,
    }

    task = _TG.create_task(_audit_task(conn, event_init, discard_repeated))

    if random() < AUDIT_CLEANUP_PROBABILITY:
        _TG.create_task(_cleanup_old_audit_logs())

    request_audit_tasks = get_request_audit_tasks()
    request_audit_tasks.add(task)

    if type not in {'auth_api', 'auth_web'} or extra:
        values: list[str] = []
        if user_id is not None:
            values.append(f'uid={user_id}')
        if target_user_id is not None:
            values.append(f'->uid={target_user_id}')
        if application_id is not None:
            values.append(f'aid={application_id}')
        logging.info('AUDIT: %s %s "%s": %s', req_ip, type, ' '.join(values), extra)

    async def _waiter():
        request_audit_tasks.discard(task)
        await task

    return _waiter()


async def _audit_task(
    conn: AsyncConnection | None,
    event_init: AuditEventInit,
    discard_repeated: timedelta | None,
):
    query = SQL("""
        INSERT INTO audit (
            id, type, ip, user_agent, user_id,
            target_user_id, application_id, token_id, extra
        )
        SELECT
            %(id)s, %(type)s, %(ip)s, %(user_agent)s, %(user_id)s,
            %(target_user_id)s, %(application_id)s, %(token_id)s, %(extra)s::jsonb
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
                AND token_id IS NOT DISTINCT FROM %(token_id)s
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

    async with db(True, conn) as conn:
        await conn.execute(
            query,
            {
                **event_init,
                'extra': (Jsonb(extra) if (extra := event_init.get('extra')) else None),
                'discard_repeated': discard_repeated,
            },
        )


async def _cleanup_old_audit_logs():
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


@cython.cfunc
def _proto_dict(message: Message):
    out: dict[str, Any] = {}

    for field, value in message.ListFields():
        if field.label == FieldDescriptor.LABEL_REPEATED:
            entries = list(value)
            if field.type == FieldDescriptor.TYPE_ENUM:
                values_by_number = field.enum_type.values_by_number
                entries = [
                    (
                        entry_def.name
                        if (entry_def := values_by_number.get(entry))
                        else entry
                    )
                    for entry in entries
                ]
            out[field.name] = entries
            continue

        if field.type == FieldDescriptor.TYPE_ENUM:
            entry_def = field.enum_type.values_by_number.get(value)
            out[field.name] = entry_def.name if entry_def is not None else value
            continue

        out[field.name] = value

    return out
