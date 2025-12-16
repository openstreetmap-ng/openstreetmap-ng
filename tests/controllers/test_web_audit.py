from datetime import timedelta
from ipaddress import ip_address

from httpx import AsyncClient
from zid import zid

from app.config import AUDIT_POLICY
from app.db import db
from app.models.types import ApplicationId
from app.services.audit_service import AuditService


async def test_audit_page_excludes_stale_events_after_cleanup(client: AsyncClient):
    app_id: ApplicationId = zid()  # type: ignore

    await AuditService.force_process()

    async with db(True) as conn:
        await conn.execute(
            """
            INSERT INTO audit (
                id, type, ip, application_id,
                created_at
            )
            VALUES (
                %(id)s, 'auth_web', %(ip)s, %(application_id)s,
                statement_timestamp() - %(age)s
            )
            """,
            {
                'id': zid(),
                'ip': ip_address('192.168.1.1'),
                'application_id': app_id,
                'age': AUDIT_POLICY.auth_web.retention + timedelta(days=1),
            },
        )
        await conn.execute(
            """
            INSERT INTO audit (
                id, type, ip, application_id,
                created_at
            )
            VALUES (
                %(id)s, 'auth_web', %(ip)s, %(application_id)s,
                statement_timestamp() - %(age)s
            )
            """,
            {
                'id': zid(),
                'ip': ip_address('192.168.1.2'),
                'application_id': app_id,
                'age': AUDIT_POLICY.auth_web.retention - timedelta(days=1),
            },
        )

    client.headers['Authorization'] = 'User admin'

    r = await client.post(
        '/api/web/audit',
        params={'application_id': app_id, 'type': 'auth_web'},
        headers={'Content-Type': 'application/x-protobuf'},
        content=b'',
    )
    assert r.status_code == 200
    assert '192.168.1.1' in r.text
    assert '192.168.1.2' in r.text
    assert 'X-StandardPagination' in r.headers

    await AuditService.force_process()

    r = await client.post(
        '/api/web/audit',
        params={'application_id': app_id, 'type': 'auth_web'},
        headers={'Content-Type': 'application/x-protobuf'},
        content=b'',
    )
    assert r.status_code == 200
    assert '192.168.1.1' not in r.text
    assert '192.168.1.2' in r.text
    assert 'X-StandardPagination' in r.headers
