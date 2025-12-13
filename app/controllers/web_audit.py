from asyncio import TaskGroup
from datetime import datetime
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import NonNegativeInt

from app.config import AUDIT_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.standard_pagination import sp_apply_headers, sp_resolve_page
from app.models.db.audit import AuditEvent, AuditType
from app.models.db.user import User
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.user_query import UserQuery

router = APIRouter(prefix='/api/web/audit')


@router.get('')
async def audit_page(
    _: Annotated[User, web_user('role_administrator')],
    page: Annotated[NonNegativeInt, Query()],
    num_items: Annotated[int | None, Query()] = None,
    ip: Annotated[
        IPv4Address | IPv6Address | IPv4Network | IPv6Network | None, Query()
    ] = None,
    user: Annotated[str | None, Query()] = None,
    application_id: Annotated[ApplicationId | None, Query()] = None,
    type: Annotated[AuditType | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
):
    sp_request_headers = num_items is None
    if sp_request_headers:
        num_items = await AuditQuery.find(  # type: ignore
            'count',
            ip=ip,
            user=user,
            application_id=application_id,
            type=type,
            created_after=created_after,
            created_before=created_before,
        )

    assert num_items is not None
    page = sp_resolve_page(
        page=page, num_items=num_items, page_size=AUDIT_LIST_PAGE_SIZE
    )

    events: list[AuditEvent] = await AuditQuery.find(  # type: ignore
        'page',
        page=page,
        num_items=num_items,
        ip=ip,
        user=user,
        application_id=application_id,
        type=type,
        created_after=created_after,
        created_before=created_before,
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(events))
        tg.create_task(
            UserQuery.resolve_users(
                events, user_id_key='target_user_id', user_key='target_user'
            )
        )
        apps = await OAuth2ApplicationQuery.resolve_applications(events)
        tg.create_task(UserQuery.resolve_users(apps))

    response = await render_response(
        'audit/page',
        {
            'events': events,
        },
    )
    if sp_request_headers:
        sp_apply_headers(response, num_items=num_items, page_size=AUDIT_LIST_PAGE_SIZE)
    return response
