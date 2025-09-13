from asyncio import TaskGroup
from datetime import datetime
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.config import AUDIT_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.audit import AUDIT_TYPE_VALUES, AuditType
from app.models.db.user import User
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.services.audit_service import audit

router = APIRouter()


@router.get('/audit')
async def audit_index(
    request: Request,
    _: Annotated[User, web_user('role_administrator')],
    ip: Annotated[
        IPv4Address | IPv6Address | IPv4Network | IPv6Network | None, Query()
    ] = None,
    user: Annotated[str | None, Query()] = None,
    application_id: Annotated[ApplicationId | None, Query()] = None,
    type: Annotated[AuditType | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
):
    async with TaskGroup() as tg:
        tg.create_task(audit('view_audit', extra={'query': request.url.query}))

        audit_num_items: int = await AuditQuery.find(  # type: ignore
            'count',
            ip=ip,
            user=user,
            application_id=application_id,
            type=type,
            created_after=created_after,
            created_before=created_before,
        )
        audit_num_pages = ceil(audit_num_items / AUDIT_LIST_PAGE_SIZE)

        return await render_response(
            'audit/index',
            {
                'AUDIT_TYPE_VALUES': AUDIT_TYPE_VALUES,
                'audit_num_items': audit_num_items,
                'audit_num_pages': audit_num_pages,
                'ip': ip or '',
                'user_q': user or '',
                'application_id': application_id or '',
                'type': type,
                'created_after': created_after.isoformat() if created_after else '',
                'created_before': created_before.isoformat() if created_before else '',
            },
        )
