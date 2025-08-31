from datetime import datetime, timedelta
from typing import Annotated, Literal

import orjson
from fastapi import APIRouter, Form, Query, Response
from pydantic import PositiveInt
from starlette import status
from starlette.responses import RedirectResponse

from app.config import ENV, USER_EXPORT_LIMIT
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.standard_feedback import StandardFeedback
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User, UserRole
from app.models.types import Password, UserId
from app.queries.audit_query import AuditQuery
from app.queries.user_query import UserQuery
from app.services.system_app_service import SystemAppService
from app.services.user_service import UserService
from app.validators.display_name import DisplayNameValidating
from app.validators.email import EmailValidating

router = APIRouter(prefix='/api/web/admin/users')


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
        'admin/users/users-page',
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


@router.post('/{user_id:int}/update')
async def update_user(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
    display_name: Annotated[DisplayNameValidating | None, Form()] = None,
    email: Annotated[EmailValidating | None, Form()] = None,
    email_verified: Annotated[bool, Form()] = False,
    roles: Annotated[list[UserRole] | None, Form()] = None,
    new_password: Annotated[Password | None, Form()] = None,
):
    await UserService.admin_update_user(
        user_id=user_id,
        display_name=display_name,
        email=email,
        email_verified=email_verified,
        roles=roles or [],
        new_password=new_password,
    )
    return StandardFeedback.success_result(None, 'User has been updated')


@router.post('/{user_id:int}/login-as')
async def login_as_user(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
):
    access_token = await SystemAppService.create_access_token(
        SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
    )

    response = RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key='auth',
        value=access_token.get_secret_value(),
        max_age=None,
        secure=ENV != 'dev',
        httponly=True,
        samesite='lax',
    )
    return response
