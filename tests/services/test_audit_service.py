from datetime import timedelta
from ipaddress import ip_address

import pytest
from zid import zid

from app.config import AUDIT_RETENTION_AUTH_WEB
from app.db import db
from app.models.db.audit import AuditEvent
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.services.audit_service import AuditService


@pytest.mark.flaky(reruns=3, only_rerun=['AssertionError'])
async def test_cleanup_old_audit_logs():
    app_id: ApplicationId = zid()  # type: ignore

    async with db(True) as conn:
        # Create old auth_web event
        await conn.execute(
            """
            INSERT INTO audit (
                id, type, ip, user_agent, user_id, application_id,
                email, display_name, extra, created_at
            )
            VALUES (
                %(id)s, 'auth_web', %(ip)s, NULL, NULL, %(application_id)s,
                NULL, NULL, NULL, statement_timestamp() - %(age)s
            )
            """,
            {
                'id': zid(),
                'ip': ip_address('192.168.1.1'),
                'application_id': app_id,
                'age': AUDIT_RETENTION_AUTH_WEB + timedelta(days=1),
            },
        )

        # Create recent auth_web event
        await conn.execute(
            """
            INSERT INTO audit (
                id, type, ip, user_agent, user_id, application_id,
                email, display_name, extra, created_at
            )
            VALUES (
                %(id)s, 'auth_web', %(ip)s, NULL, NULL, %(application_id)s,
                NULL, NULL, NULL, statement_timestamp() - %(age)s
            )
            """,
            {
                'id': zid(),
                'ip': ip_address('192.168.1.2'),
                'application_id': app_id,
                'age': AUDIT_RETENTION_AUTH_WEB - timedelta(days=1),
            },
        )

    # Verify both events exist before cleanup
    events_before: list[AuditEvent] = await AuditQuery.find(  # type: ignore
        'page',
        page=1,
        num_items=10,
        application_id=app_id,
        type='auth_web',
    )
    assert len(events_before) == 2

    # Force the cleanup process
    await AuditService.force_process()

    # Verify only the recent event remains after cleanup
    events_after: list[AuditEvent] = await AuditQuery.find(  # type: ignore
        'page',
        page=1,
        num_items=10,
        application_id=app_id,
        type='auth_web',
    )
    assert len(events_after) == 1

    # Verify it's the recent event that remained
    remaining_event = events_after[0]
    assert remaining_event['ip'] == ip_address('192.168.1.2')
