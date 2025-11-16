from asyncio import TaskGroup
from datetime import datetime, timedelta
from typing import Annotated, Literal

import orjson
from fastapi import APIRouter, Cookie, Form, HTTPException, Query, Response
from pydantic import PositiveInt, SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import ADMIN_USER_EXPORT_LIMIT, ENV
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.standard_feedback import StandardFeedback
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User, UserRole
from app.models.types import ApplicationId, Password, UserId
from app.queries.audit_query import AuditQuery
from app.queries.user_query import UserQuery
from app.services.audit_service import audit
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.system_app_service import SystemAppService
from app.services.user_service import UserService
from app.services.user_totp_service import UserTOTPService
from app.validators.display_name import DisplayNameValidating
from app.validators.email import EmailValidating

router = APIRouter(prefix='/api/web/admin/users')


@router.get('')
async def users_page(
    _: Annotated[User, web_user('role_administrator')],
    page: Annotated[PositiveInt, Query()],
    num_items: Annotated[PositiveInt, Query()],
    search: Annotated[str | None, Query()] = None,
    unverified: Annotated[bool | None, Query()] = None,
    roles: Annotated[list[UserRole] | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    application_id: Annotated[ApplicationId | None, Query()] = None,
    sort: Annotated[
        Literal['created_asc', 'created_desc', 'name_asc', 'name_desc'], Query()
    ] = 'created_desc',
):
    users: list[User] = await UserQuery.find(  # type: ignore
        'page',
        page=page,
        num_items=num_items,
        search=search,
        unverified=True if unverified else None,
        roles=roles,
        created_after=created_after,
        created_before=created_before,
        application_id=application_id,
        sort=sort,
    )

    ip_counts = await AuditQuery.count_ip_by_user(
        [user['id'] for user in users], since=timedelta(days=1), ignore_app_events=True
    )

    return await render_response(
        'admin/users/page',
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
    application_id: Annotated[ApplicationId | None, Query()] = None,
):
    user_ids: list[UserId] = await UserQuery.find(  # type: ignore
        'ids',
        search=search,
        unverified=True if unverified else None,
        roles=roles,
        created_after=created_after,
        created_before=created_before,
        application_id=application_id,
        limit=ADMIN_USER_EXPORT_LIMIT,
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
    return StandardFeedback.success_result(
        None,
        'User has been updated'
        if ENV != 'test'
        else 'User would have been updated. This feature is disabled in the test environment.',
    )


@router.post('/{user_id:int}/impersonate')
async def impersonate_user(
    _: Annotated[User, web_user('role_administrator')],
    auth: Annotated[SecretStr, Cookie()],
    user_id: UserId,
):
    if ENV == 'test':
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            'Impersonation is disabled in the test environment',
        )

    async with TaskGroup() as tg:
        tg.create_task(OAuth2TokenService.revoke_by_access_token(auth))
        access_token = await SystemAppService.create_access_token(
            SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id, hidden=True
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
    await audit('impersonate', target_user_id=user_id)
    return response


@router.post('/{user_id:int}/remove-totp')
async def remove_user_totp(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
):
    """Forcefully remove TOTP 2FA for a user (admin action)."""
    # Admin removal doesn't require password - use empty password
    # The service will recognize this as an admin action
    await UserTOTPService.remove_totp(
        password=Password(SecretStr('')),  # Dummy password for admin
        target_user_id=user_id,
    )
    return Response(None, status.HTTP_204_NO_CONTENT)
