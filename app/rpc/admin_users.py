from asyncio import TaskGroup
from collections.abc import Iterable
from datetime import timedelta
from http.cookies import SimpleCookie
from typing import Literal, override

from connectrpc.request import RequestContext
from pydantic import SecretStr
from starlette.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from app.config import ADMIN_USER_EXPORT_LIMIT, ADMIN_USER_LIST_PAGE_SIZE, ENV
from app.lib.auth_context import require_web_user
from app.lib.date_utils import datetime_unix, unix_datetime
from app.lib.standard_feedback import StandardFeedback
from app.lib.standard_pagination import sp_paginate_table
from app.middlewares.request_context_middleware import get_request
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import (
    User,
    user_avatar_url,
    user_is_deleted,
)
from app.models.proto.admin_users_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.admin_users_pb2 import (
    Account,
    ExportIdsRequest,
    ExportIdsResponse,
    Filters,
    ImpersonateRequest,
    ImpersonateResponse,
    ListRequest,
    ListResponse,
    ResetTwoFactorRequest,
    ResetTwoFactorResponse,
    TwoFactorStatus,
    UpdateRequest,
    UpdateResponse,
)
from app.models.proto.admin_users_pb2 import Role as ProtoRole
from app.models.proto.admin_users_types import Role
from app.models.proto.shared_pb2 import IpCount
from app.models.types import ApplicationId, DisplayName, Email, UserId
from app.queries.audit_query import AuditQuery
from app.queries.user_passkey_query import UserPasskeyQuery
from app.queries.user_query import UserQuery
from app.services.audit_service import audit
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.system_app_service import SystemAppService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_service import UserService
from app.services.user_totp_service import UserTOTPService


class _Service(Service):
    @override
    async def list(self, request: ListRequest, ctx: RequestContext):
        require_web_user('role_administrator')
        audit(
            'view_admin_users',
            extra_proto=request.filters,
            extra={'action': 'list'},
        ).close()

        (
            search,
            unverified,
            roles,
            created_after,
            created_before,
            application_id,
            sort,
        ) = _filters_parse(request.filters)

        where_clause, params = UserQuery.where_clause(
            search=search,
            unverified=unverified,
            roles=roles,
            created_after=created_after,
            created_before=created_before,
            application_id=application_id,
        )

        cursor_column: Literal['created_at', 'display_name']
        cursor_kind: Literal['datetime', 'text']
        order_dir: Literal['asc', 'desc']
        if sort == Filters.Sort.created_desc:
            cursor_column = 'created_at'
            cursor_kind = 'datetime'
            order_dir = 'desc'
        elif sort == Filters.Sort.created_asc:
            cursor_column = 'created_at'
            cursor_kind = 'datetime'
            order_dir = 'asc'
        elif sort == Filters.Sort.name_asc:
            cursor_column = 'display_name'
            cursor_kind = 'text'
            order_dir = 'asc'
        else:
            cursor_column = 'display_name'
            cursor_kind = 'text'
            order_dir = 'desc'

        users, state = await sp_paginate_table(
            User,
            request.state.SerializeToString(),
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
            tfa_status_t = tg.create_task(UserQuery.get_2fa_status(user_ids))
            ip_counts_t = tg.create_task(
                AuditQuery.count_ip_by_user(
                    user_ids, since=timedelta(days=1), ignore_app_events=True, limit=10
                )
            )

        tfa_status = tfa_status_t.result()
        ip_counts = ip_counts_t.result()

        entries = [
            ListResponse.Entry(
                account=Account(
                    id=user['id'],
                    display_name=user['display_name'],
                    avatar_url=user_avatar_url(user),
                    email=user['email'],
                    email_verified=user['email_verified'],
                    roles=user['roles'],
                    created_at=int(user['created_at'].timestamp()),
                    scheduled_delete_at=datetime_unix(user['scheduled_delete_at']),
                    deleted=user_is_deleted(user),
                ),
                two_factor_status=TwoFactorStatus(
                    has_passkeys=tfa_status[user['id']]['has_passkeys'],
                    has_totp=tfa_status[user['id']]['has_totp'],
                    has_recovery=tfa_status[user['id']]['has_recovery'],
                ),
                ip_counts=[
                    IpCount(ip=ip.packed, count=count)
                    for ip, count in ip_counts.get(user['id'], ())
                ],
            )
            for user in users
        ]

        return ListResponse(entries=entries, state=state)

    @override
    async def export_ids(self, request: ExportIdsRequest, ctx: RequestContext):
        require_web_user('role_administrator')
        search, unverified, roles, created_after, created_before, application_id, _ = (
            _filters_parse(request.filters)
        )

        user_ids = await UserQuery.find_ids(
            limit=ADMIN_USER_EXPORT_LIMIT,
            search=search,
            unverified=unverified,
            roles=roles,
            created_after=created_after,
            created_before=created_before,
            application_id=application_id,
            sort='created_desc',
        )
        audit(
            'view_admin_users',
            extra_proto=request.filters,
            extra={'action': 'export', 'count': len(user_ids)},
        ).close()

        return ExportIdsResponse(ids=user_ids)

    @override
    async def update(self, request: UpdateRequest, ctx: RequestContext):
        require_web_user('role_administrator')

        await UserService.admin_update_user(
            user_id=UserId(request.user_id),
            display_name=(
                DisplayName(request.display_name)
                if request.HasField('display_name')
                else None
            ),
            email=Email(request.email) if request.HasField('email') else None,
            email_verified=request.email_verified,
            roles=_roles_from_proto(request.roles),
            new_password=(
                request.new_password if request.HasField('new_password') else None
            ),
        )

        return UpdateResponse(
            feedback=StandardFeedback.success_feedback(
                None,
                (
                    'User has been updated'
                    if ENV != 'test'
                    else 'User would have been updated. This feature is disabled in the test environment.'
                ),
            )
        )

    @override
    async def reset_two_factor(
        self, request: ResetTwoFactorRequest, ctx: RequestContext
    ):
        require_web_user('role_administrator')
        user_id = UserId(request.user_id)

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

        return ResetTwoFactorResponse()

    @override
    async def impersonate(self, request: ImpersonateRequest, ctx: RequestContext):
        require_web_user('role_administrator')

        if ENV == 'test':
            raise HTTPException(
                HTTP_403_FORBIDDEN,
                'Impersonation is disabled in the test environment',
            )

        auth_cookie = get_request().cookies.get('auth')
        if auth_cookie is None:
            raise HTTPException(HTTP_401_UNAUTHORIZED, 'Missing auth cookie')

        user_id = UserId(request.user_id)
        audit('impersonate', target_user_id=user_id).close()
        async with TaskGroup() as tg:
            tg.create_task(
                OAuth2TokenService.revoke_by_access_token(SecretStr(auth_cookie))
            )
            access_token = await SystemAppService.create_access_token(
                client_id=SYSTEM_APP_WEB_CLIENT_ID,
                user_id=user_id,
                hidden=True,
            )

        _set_auth_cookie_header(ctx, access_token.token)
        return ImpersonateResponse(redirect_url='/')


def _roles_from_proto(roles: Iterable[int]) -> list[Role]:
    return list(dict.fromkeys(ProtoRole.Name(role) for role in roles))


def _filters_parse(filters: Filters):
    search = filters.search if filters.HasField('search') else None
    unverified = True if filters.unverified else None
    roles = _roles_from_proto(filters.roles) or None
    created_after = (
        unix_datetime(filters.created_after)
        if filters.HasField('created_after')
        else None
    )
    created_before = (
        unix_datetime(filters.created_before)
        if filters.HasField('created_before')
        else None
    )
    application_id = (
        ApplicationId(filters.application_id)
        if filters.HasField('application_id')
        else None
    )

    sort = filters.sort

    return (
        search,
        unverified,
        roles,
        created_after,
        created_before,
        application_id,
        sort,
    )


def _set_auth_cookie_header(ctx: RequestContext, token: SecretStr):
    cookie = SimpleCookie()
    cookie['auth'] = token.get_secret_value()
    cookie['auth']['path'] = '/'
    cookie['auth']['httponly'] = True
    cookie['auth']['samesite'] = 'lax'
    if ENV != 'dev':
        cookie['auth']['secure'] = True
    ctx.response_headers()['Set-Cookie'] = cookie.output(header='').lstrip()


service = _Service()
asgi_app_cls = ServiceASGIApplication
