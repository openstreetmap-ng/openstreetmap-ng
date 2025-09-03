from asyncio import TaskGroup
from datetime import datetime
from math import ceil
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from starlette import status

from app.config import DISPLAY_NAME_MAX_LENGTH, PASSWORD_MIN_LENGTH, USER_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import USER_ROLES, User, UserRole
from app.models.types import UserId
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/admin/users')
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
    users_num_items: int = await UserQuery.find(  # type: ignore
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
        'admin/users/index',
        {
            'users_num_items': users_num_items,
            'users_num_pages': users_num_pages,
            'search': search or '',
            'unverified': unverified,
            'roles': roles or (),
            'created_after': created_after.isoformat() if created_after else '',
            'created_before': created_before.isoformat() if created_before else '',
            'sort': sort,
        },
    )


@router.get('/admin/users/{user_id:int}')
async def user_edit(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
):
    edit_user = await UserQuery.find_by_id(user_id)
    if edit_user is None:
        return Response(None, status.HTTP_404_NOT_FOUND)

    async with TaskGroup() as tg:
        connected_providers_task = tg.create_task(
            ConnectedAccountQuery.get_providers_by_user(user_id)
        )
        applications_task = tg.create_task(OAuth2ApplicationQuery.find_by_user(user_id))
        tokens_task = tg.create_task(OAuth2TokenQuery.find_pats_by_user(user_id))
        authorizations = await OAuth2TokenQuery.find_unique_per_app_by_user(user_id)
        tg.create_task(OAuth2ApplicationQuery.resolve_applications(authorizations))

    return await render_response(
        'admin/users/edit',
        {
            'edit_user': edit_user,
            'connected_providers': connected_providers_task.result(),
            'authorizations': authorizations,
            'applications': applications_task.result(),
            'tokens': tokens_task.result(),
            'DISPLAY_NAME_MAX_LENGTH': DISPLAY_NAME_MAX_LENGTH,
            'PASSWORD_MIN_LENGTH': PASSWORD_MIN_LENGTH,
            'USER_ROLES': USER_ROLES,
        },
    )
