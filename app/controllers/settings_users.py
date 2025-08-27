from datetime import datetime
from math import ceil
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.config import USER_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User, UserRole
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/settings/users')
async def users_index(
    _: Annotated[User, web_user('role_administrator')],
    search: Annotated[str | None, Query()] = None,
    unverified: Annotated[bool | None, Query()] = None,
    roles: Annotated[list[UserRole] | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    sort: Annotated[
        Literal['created_asc', 'created_desc', 'name_asc', 'name_desc'], Query()
    ] = 'created_desc',
):
    users_num_items: int = await UserQuery.find_filtered(  # type: ignore
        'count',
        search=search,
        unverified=True if unverified else None,
        roles=roles,
        created_after=created_after,
        created_before=created_before,
        sort=sort,
    )
    users_num_pages = ceil(users_num_items / USER_LIST_PAGE_SIZE)

    return await render_response(
        'settings/users/index',
        {
            'users_num_items': users_num_items,
            'users_num_pages': users_num_pages,
            'search': search,
            'unverified': unverified,
            'roles': roles,
            'created_after': (
                created_after.isoformat() if created_after is not None else ''
            ),
            'created_before': (
                created_before.isoformat() if created_before is not None else ''
            ),
            'sort': sort,
        },
    )
