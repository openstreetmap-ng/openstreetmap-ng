from datetime import timedelta
from ipaddress import ip_address

from zid import zid

from app.config import AUDIT_POLICY
from app.db import db
from app.models.db.audit import AuditEvent
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.services.audit_service import AuditService


async def test_cleanup_old_audit_logs():
    # Arrange: Insert two audit events: one stale and one recent
    app_id: ApplicationId = zid()  # type: ignore

    async with db(True) as conn:
        # Create old auth_web event
        await conn.execute(
            """
            INSERT INTO audit (
                type, ip, application_id,
                created_at
            )
            VALUES (
                'auth_web', %(ip)s, %(application_id)s,
                statement_timestamp() - %(age)s
            )
            """,
            {
                'ip': ip_address('192.168.1.1'),
                'application_id': app_id,
                'age': AUDIT_POLICY.auth_web.retention + timedelta(days=1),
            },
        )

        # Create recent auth_web event
        await conn.execute(
            """
            INSERT INTO audit (
                type, ip, application_id,
                created_at
            )
            VALUES (
                'auth_web', %(ip)s, %(application_id)s,
                statement_timestamp() - %(age)s
            )
            """,
            {
                'ip': ip_address('192.168.1.2'),
                'application_id': app_id,
                'age': AUDIT_POLICY.auth_web.retention - timedelta(days=1),
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

    # Act: Force the cleanup process
    await AuditService.force_process()

    # Assert: Verify only the recent event remains after cleanup
    events_after: list[AuditEvent] = await AuditQuery.find(  # type: ignore
        'page',
        page=1,
        num_items=10,
        application_id=app_id,
        type='auth_web',
    )
    assert len(events_after) == 1
    assert events_after[0]['ip'] == ip_address('192.168.1.2')
