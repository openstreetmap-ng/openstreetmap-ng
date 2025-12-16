from asyncio import TaskGroup
from datetime import datetime, timedelta
from typing import Annotated, Literal

import orjson
from fastapi import APIRouter, Cookie, File, Form, HTTPException, Query, Response
from pydantic import SecretStr
from starlette import status
from starlette.responses import RedirectResponse

from app.config import ADMIN_USER_EXPORT_LIMIT, ADMIN_USER_LIST_PAGE_SIZE, ENV
from app.lib.auth_context import web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response,
)
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import User, UserRole
from app.models.types import ApplicationId, Password, UserId
from app.queries.audit_query import AuditQuery
from app.queries.user_passkey_query import UserPasskeyQuery
from app.queries.user_query import UserQuery
from app.services.audit_service import audit
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.system_app_service import SystemAppService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_service import UserService
from app.services.user_totp_service import UserTOTPService
from app.validators.display_name import DisplayNameValidating
from app.validators.email import EmailValidating

router = APIRouter(prefix='/api/web/admin/users')


@router.post('')
async def users_page(
    _: Annotated[User, web_user('role_administrator')],
    search: Annotated[str | None, Query()] = None,
    unverified: Annotated[bool | None, Query()] = None,
    roles: Annotated[list[UserRole] | None, Query()] = None,
    created_after: Annotated[datetime | None, Query()] = None,
    created_before: Annotated[datetime | None, Query()] = None,
    application_id: Annotated[ApplicationId | None, Query()] = None,
    sort: Annotated[
        Literal['created_asc', 'created_desc', 'name_asc', 'name_desc'], Query()
    ] = 'created_desc',
    sp_state: StandardPaginationStateBody = b'',
):
    where_clause, params = UserQuery.where_clause(
        search=search,
        unverified=True if unverified else None,
        roles=roles,
        created_after=created_after,
        created_before=created_before,
        application_id=application_id,
    )

    cursor_column: Literal['created_at', 'display_name']
    cursor_kind: Literal['datetime', 'text']
    order_dir: Literal['asc', 'desc']
    if sort == 'created_desc':
        cursor_column = 'created_at'
        cursor_kind = 'datetime'
        order_dir = 'desc'
    elif sort == 'created_asc':
        cursor_column = 'created_at'
        cursor_kind = 'datetime'
        order_dir = 'asc'
    elif sort == 'name_asc':
        cursor_column = 'display_name'
        cursor_kind = 'text'
        order_dir = 'asc'
    elif sort == 'name_desc':
        cursor_column = 'display_name'
        cursor_kind = 'text'
        order_dir = 'desc'
    else:
        raise NotImplementedError(f'Unsupported sort {sort!r}')

    users, state = await sp_paginate_table(
        User,
        sp_state,
        table='user',
        where=where_clause,
        params=params,
        page_size=ADMIN_USER_LIST_PAGE_SIZE,
        cursor_column=cursor_column,
        cursor_kind=cursor_kind,
        order_dir=order_dir,
    )

    user_ids = [user['id'] for user in users]
    async with TaskGroup() as tg:
        two_fa_status_t = tg.create_task(UserQuery.get_2fa_status(user_ids))
        ip_counts_t = tg.create_task(
            AuditQuery.count_ip_by_user(
                user_ids, since=timedelta(days=1), ignore_app_events=True
            )
        )

    return await sp_render_response(
        'admin/users/page',
        {
            'users': users,
            'two_fa_status': two_fa_status_t.result(),
            'ip_counts': ip_counts_t.result(),
        },
        state,
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
    user_ids = await UserQuery.find_ids(
        limit=ADMIN_USER_EXPORT_LIMIT,
        search=search,
        unverified=True if unverified else None,
        roles=roles,
        created_after=created_after,
        created_before=created_before,
        application_id=application_id,
        sort='created_desc',
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
    new_password: Annotated[Password | None, File()] = None,
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


@router.post('/{user_id:int}/reset-2fa')
async def reset_user_2fa(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
):
    """Reset 2FA methods for a user (passkeys and TOTP)."""
    passkeys = await UserPasskeyQuery.find_all_by_user_id(
        user_id, resolve_aaguid_db=False
    )

    async with TaskGroup() as tg:
        for passkey in passkeys:
            tg.create_task(
                UserPasskeyService.remove_passkey(
                    passkey['credential_id'], password=None, user_id=user_id
                )
            )
        tg.create_task(UserTOTPService.remove_totp(password=None, user_id=user_id))

    return Response(None, status.HTTP_204_NO_CONTENT)


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
        value=access_token.token.get_secret_value(),
        max_age=None,
        secure=ENV != 'dev',
        httponly=True,
        samesite='lax',
    )
    await audit('impersonate', target_user_id=user_id)
    return response
