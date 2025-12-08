from asyncio import TaskGroup
from datetime import datetime
from math import ceil
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request

from app.config import ADMIN_APPLICATION_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.services.audit_service import audit

router = APIRouter()


@router.get('/admin/applications')
async def applications_index(
    request: Request,
    _: Annotated[User, web_user('role_administrator')],
    search: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
    interacted_user: Annotated[str | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    sort: Annotated[Literal['created_asc', 'created_desc'], Query()] = 'created_desc',
):
    async with TaskGroup() as tg:
        tg.create_task(
            audit('view_admin_applications', extra={'query': request.url.query})
        )

        apps_num_items: int = await OAuth2ApplicationQuery.find(  # type: ignore
            'count',
            search=search,
            owner=owner,
            interacted_user=interacted_user,
            created_after=created_after,
            created_before=created_before,
            sort=sort,
        )
        apps_num_pages = ceil(apps_num_items / ADMIN_APPLICATION_LIST_PAGE_SIZE)

        # Build pagination action URL with current filters
        pagination_params: dict[str, str] = {'sort': sort}
        if search:
            pagination_params['search'] = search
        if owner:
            pagination_params['owner'] = owner
        if interacted_user:
            pagination_params['interacted_user'] = interacted_user
        if created_after:
            pagination_params['created_after'] = created_after.isoformat()
        if created_before:
            pagination_params['created_before'] = created_before.isoformat()
        pagination_action = (
            f'/api/web/admin/applications?{urlencode(pagination_params)}'
        )

        return await render_response(
            'admin/applications/index',
            {
                'apps_num_items': apps_num_items,
                'apps_num_pages': apps_num_pages,
                'pagination_action': pagination_action,
                'search': search or '',
                'owner': owner or '',
                'interacted_user': interacted_user or '',
                'created_after': created_after.isoformat() if created_after else '',
                'created_before': created_before.isoformat() if created_before else '',
                'sort': sort,
            },
        )
