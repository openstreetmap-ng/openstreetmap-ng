from datetime import timedelta
from ipaddress import ip_address

from httpx import AsyncClient
from zid import zid

from app.config import AUDIT_POLICY
from app.db import db
from app.models.proto.audit_pb2 import (
    Filters,
    ListRequest,
    ListResponse,
)
from app.models.types import ApplicationId
from app.services.audit_service import _cleanup_old_audit_logs


async def test_list_audit_events_requires_admin(client: AsyncClient):
    client.headers['Authorization'] = 'User user1'

    r = await client.post(
        '/rpc/audit.Service/List',
        headers={'Content-Type': 'application/proto'},
        content=ListRequest(filters=Filters()).SerializeToString(),
    )

    assert r.status_code == 403, r.text


async def test_list_audit_events_excludes_stale_events_after_cleanup(
    client: AsyncClient,
):
    app_id: ApplicationId = zid()  # type: ignore

    await _cleanup_old_audit_logs()

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
        '/rpc/audit.Service/List',
        headers={'Content-Type': 'application/proto'},
        content=ListRequest(
            filters=Filters(
                application_id=app_id,
                type='auth_web',
            )
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    first_page = ListResponse.FromString(r.content)
    first_page_ips = {event.ip for event in first_page.events}
    assert ip_address('192.168.1.1').packed in first_page_ips
    assert ip_address('192.168.1.2').packed in first_page_ips

    await _cleanup_old_audit_logs()

    r = await client.post(
        '/rpc/audit.Service/List',
        headers={'Content-Type': 'application/proto'},
        content=ListRequest(
            filters=Filters(
                application_id=app_id,
                type='auth_web',
            )
        ).SerializeToString(),
    )
    assert r.is_success, r.text
    second_page = ListResponse.FromString(r.content)
    second_page_ips = {event.ip for event in second_page.events}
    assert ip_address('192.168.1.1').packed not in second_page_ips
    assert ip_address('192.168.1.2').packed in second_page_ips
