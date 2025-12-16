from asyncio import TaskGroup
from datetime import datetime, timedelta
from typing import Annotated, Literal

import orjson
from fastapi import APIRouter, Query
from starlette.responses import Response

from app.config import ADMIN_APPLICATION_EXPORT_LIMIT, ADMIN_APPLICATION_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response,
)
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import User
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

router = APIRouter(prefix='/api/web/admin/applications')


@router.post('')
async def applications_page(
    _: Annotated[User, web_user('role_administrator')],
    search: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
    interacted_user: Annotated[str | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    sort: Annotated[Literal['created_asc', 'created_desc'], Query()] = 'created_desc',
    sp_state: StandardPaginationStateBody = b'',
):
    where_clause, params = await OAuth2ApplicationQuery.where_clause(
        search=search,
        owner=owner,
        interacted_user=interacted_user,
        created_after=created_after,
        created_before=created_before,
    )

    order_dir: Literal['asc', 'desc']
    if sort == 'created_desc':
        order_dir = 'desc'
    elif sort == 'created_asc':
        order_dir = 'asc'
    else:
        raise NotImplementedError(f'Unsupported sort {sort!r}')

    apps, state = await sp_paginate_table(
        OAuth2Application,
        sp_state,
        table='oauth2_application',
        where=where_clause,
        params=params,
        page_size=ADMIN_APPLICATION_LIST_PAGE_SIZE,
        cursor_column='created_at',
        cursor_kind='datetime',
        order_dir=order_dir,
    )
    app_ids: list[ApplicationId] = [app['id'] for app in apps]

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(apps))
        ip_counts_t = tg.create_task(
            AuditQuery.count_ip_by_application(app_ids, since=timedelta(days=1))
        )
        user_counts_t = tg.create_task(
            OAuth2TokenQuery.count_users_by_applications(app_ids)
        )

    return await sp_render_response(
        'admin/applications/page',
        {
            'apps': apps,
            'ip_counts': ip_counts_t.result(),
            'user_counts': user_counts_t.result(),
        },
        state,
    )


@router.get('/export')
async def export_ids(
    _: Annotated[User, web_user('role_administrator')],
    search: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
    interacted_user: Annotated[str | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
):
    app_ids: list[ApplicationId] = await OAuth2ApplicationQuery.find_ids(
        limit=ADMIN_APPLICATION_EXPORT_LIMIT,
        search=search,
        owner=owner,
        interacted_user=interacted_user,
        created_after=created_after,
        created_before=created_before,
        sort='created_desc',
    )

    return Response(
        orjson.dumps(app_ids),
        media_type='application/json',
        headers={'Content-Disposition': 'attachment; filename="app-ids.json"'},
    )
