from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Query

from app.config import AUDIT_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.audit import AuditType
from app.models.db.user import User
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery

router = APIRouter()


@router.get('/audit')
async def audit_index(
    _: Annotated[User, web_user('role_administrator')],
    ip: Annotated[
        IPv4Address | IPv6Address | IPv4Network | IPv6Network | None, Query()
    ] = None,
    user: Annotated[str | None, Query()] = None,
    application_id: Annotated[ApplicationId | None, Query()] = None,
    type: Annotated[AuditType | None, Query()] = None,
):
    audit_num_items: int = await AuditQuery.find(  # type: ignore
        'count',
        ip=ip,
        user=user,
        application_id=application_id,
        type=type,
    )
    audit_num_pages = ceil(audit_num_items / AUDIT_LIST_PAGE_SIZE)

    return await render_response(
        'audit/index',
        {
            'audit_num_items': audit_num_items,
            'audit_num_pages': audit_num_pages,
            'ip': ip or '',
            'user_q': user or '',
            'application_id': application_id or '',
            'type': type,
        },
    )
