from asyncio import TaskGroup
from datetime import datetime
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Annotated

from fastapi import APIRouter, Query

from app.config import AUDIT_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response,
)
from app.models.db.audit import AuditEvent, AuditType
from app.models.db.user import User
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.user_query import UserQuery

router = APIRouter(prefix='/api/web/audit')


@router.post('')
async def audit_page(
    _: Annotated[User, web_user('role_administrator')],
    ip: Annotated[
        IPv4Address | IPv6Address | IPv4Network | IPv6Network | None, Query()
    ] = None,
    user: Annotated[str | None, Query()] = None,
    application_id: Annotated[ApplicationId | None, Query()] = None,
    type: Annotated[AuditType | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    sp_state: StandardPaginationStateBody = b'',
):
    where_clause, params = await AuditQuery.where_clause(
        ip=ip,
        user=user,
        application_id=application_id,
        type=type,
        created_after=created_after,
        created_before=created_before,
    )

    events, state = await sp_paginate_table(
        AuditEvent,
        sp_state,
        table='audit',
        where=where_clause,
        params=params,
        page_size=AUDIT_LIST_PAGE_SIZE,
        cursor_column='created_at',
        cursor_kind='datetime',
        order_dir='desc',
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

    return await sp_render_response(
        'audit/page',
        {
            'events': events,
        },
        state,
    )
