from asyncio import TaskGroup
from datetime import datetime, timedelta
from typing import Annotated, Literal

import orjson
from fastapi import APIRouter, Query
from pydantic import NonNegativeInt
from starlette.responses import Response

from app.config import ADMIN_APPLICATION_EXPORT_LIMIT, ADMIN_APPLICATION_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.standard_pagination import sp_apply_headers, sp_resolve_page
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.user import User
from app.models.types import ApplicationId
from app.queries.audit_query import AuditQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

router = APIRouter(prefix='/api/web/admin/applications')


@router.get('')
async def applications_page(
    _: Annotated[User, web_user('role_administrator')],
    page: Annotated[NonNegativeInt, Query()],
    num_items: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
    interacted_user: Annotated[str | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    sort: Annotated[Literal['created_asc', 'created_desc'], Query()] = 'created_desc',
):
    sp_request_headers = num_items is None
    if sp_request_headers:
        num_items = await OAuth2ApplicationQuery.find(
            'count',
            search=search,
            owner=owner,
            interacted_user=interacted_user,
            created_after=created_after,
            created_before=created_before,
            sort=sort,
        )

    assert num_items is not None
    page = sp_resolve_page(
        page=page, num_items=num_items, page_size=ADMIN_APPLICATION_LIST_PAGE_SIZE
    )

    apps: list[OAuth2Application] = await OAuth2ApplicationQuery.find(
        'page',
        page=page,
        num_items=num_items,
        search=search,
        owner=owner,
        interacted_user=interacted_user,
        created_after=created_after,
        created_before=created_before,
        sort=sort,
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

    response = await render_response(
        'admin/applications/page',
        {
            'apps': apps,
            'ip_counts': ip_counts_t.result(),
            'user_counts': user_counts_t.result(),
        },
    )
    if sp_request_headers:
        sp_apply_headers(
            response, num_items=num_items, page_size=ADMIN_APPLICATION_LIST_PAGE_SIZE
        )
    return response


@router.get('/export')
async def export_ids(
    _: Annotated[User, web_user('role_administrator')],
    search: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
    interacted_user: Annotated[str | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
):
    app_ids: list[ApplicationId] = await OAuth2ApplicationQuery.find(
        'ids',
        search=search,
        owner=owner,
        interacted_user=interacted_user,
        created_after=created_after,
        created_before=created_before,
        limit=ADMIN_APPLICATION_EXPORT_LIMIT,
    )

    return Response(
        orjson.dumps(app_ids),
        media_type='application/json',
        headers={'Content-Disposition': 'attachment; filename="app-ids.json"'},
    )
