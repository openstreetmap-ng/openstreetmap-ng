from datetime import datetime, timedelta
from typing import Annotated, Literal

import orjson
from fastapi import APIRouter, Query, Response
from pydantic import PositiveInt

from app.config import USER_EXPORT_LIMIT
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User, UserRole
from app.models.types import UserId
from app.queries.audit_query import AuditQuery
from app.queries.user_query import UserQuery

router = APIRouter(prefix='/api/web/settings/users')


@router.get('/')
async def users_page(
    _: Annotated[User, web_user('role_administrator')],
    page: Annotated[PositiveInt, Query()],
    num_items: Annotated[PositiveInt, Query()],
    search: Annotated[str | None, Query()] = None,
    unverified: Annotated[bool | None, Query()] = None,
    roles: Annotated[list[UserRole] | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    sort: Annotated[
        Literal['created_asc', 'created_desc', 'name_asc', 'name_desc'], Query()
    ] = 'created_desc',
):
    """Get a page of users for the management interface."""
    users: list[User] = await UserQuery.find(  # type: ignore
        'page',
        page=page,
        num_items=num_items,
        search=search,
        unverified=True if unverified else None,
        roles=roles,
        created_after=created_after,
        created_before=created_before,
        sort=sort,
    )

    user_ids = [user['id'] for user in users]
    ip_counts = await AuditQuery.count_ip_by_user(user_ids, since=timedelta(days=1))

    return await render_response(
        'settings/users/users-page',
        {
            'users': users,
            'ip_counts': ip_counts,
        },
    )


@router.get('/export')
async def export_ids(
    _: Annotated[User, web_user('role_administrator')],
    search: Annotated[str | None, Query()] = None,
    unverified: Annotated[bool | None, Query()] = None,
    roles: Annotated[list[UserRole] | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
):
    """Export user IDs matching the filters."""
    user_ids: list[UserId] = await UserQuery.find(  # type: ignore
        'ids',
        search=search,
        unverified=True if unverified else None,
        roles=roles,
        created_after=created_after,
        created_before=created_before,
        limit=USER_EXPORT_LIMIT,
    )

    return Response(
        orjson.dumps(user_ids),
        media_type='application/json',
        headers={'Content-Disposition': 'attachment; filename="user-ids.json"'},
    )
