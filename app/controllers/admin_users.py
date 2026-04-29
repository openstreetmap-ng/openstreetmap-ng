from asyncio import TaskGroup
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Response
from starlette import status

from app.lib.auth_context import web_user
from app.lib.date_utils import datetime_unix
from app.lib.render_response import render_proto_page
from app.models.db.oauth2_application import (
    SYSTEM_APP_PAT_CLIENT_ID,
    OAuth2Application,
    oauth2_app_avatar_url,
)
from app.models.db.user import (
    User,
    user_avatar_url,
    user_is_deleted,
    user_proto,
)
from app.models.proto.admin_users_pb2 import (
    Account,
    EditPage,
    Page,
    TwoFactorStatus,
)
from app.models.proto.settings_applications_pb2 import Application, Token
from app.models.types import UserId
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery
from app.services.audit_service import audit

router = APIRouter()


@router.get('/admin/users')
async def users_index(_: Annotated[User, web_user('role_administrator')]):
    return await render_proto_page(
        Page(),
        title_prefix='Users',
    )


@router.get('/admin/users/{user_id:int}')
async def user_edit(
    _: Annotated[User, web_user('role_administrator')],
    user_id: UserId,
):
    edit_user = await UserQuery.find_by_id(user_id)
    if edit_user is None:
        return Response(None, status.HTTP_404_NOT_FOUND)

    audit('view_admin_users', target_user_id=user_id).close()

    async with TaskGroup() as tg:
        tfa_status_t = tg.create_task(UserQuery.get_2fa_status([user_id]))
        accounts_t = tg.create_task(ConnectedAccountQuery.find_by_user(user_id))
        apps_t = tg.create_task(OAuth2ApplicationQuery.find_by_user(user_id))
        tokens_t = tg.create_task(OAuth2TokenQuery.find_pats_by_user(user_id))
        auths = await OAuth2TokenQuery.find_unique_per_app_by_user(user_id)
        auths_apps = await OAuth2ApplicationQuery.resolve_applications(auths)
        tg.create_task(UserQuery.resolve_users(auths_apps))

    tfa_status = tfa_status_t.result()[user_id]

    return await render_proto_page(
        EditPage(
            account=Account(
                id=edit_user['id'],
                display_name=edit_user['display_name'],
                avatar_url=user_avatar_url(edit_user),
                email=edit_user['email'],
                email_verified=edit_user['email_verified'],
                roles=edit_user['roles'],
                created_at=int(edit_user['created_at'].timestamp()),
                scheduled_delete_at=datetime_unix(edit_user['scheduled_delete_at']),
                deleted=user_is_deleted(edit_user),
            ),
            two_factor_status=TwoFactorStatus(
                has_passkeys=tfa_status['has_passkeys'],
                has_totp=tfa_status['has_totp'],
                has_recovery=tfa_status['has_recovery'],
            ),
            connected_accounts=[
                EditPage.ConnectedAccount(
                    provider=account['provider'],
                    uid=account['uid'],
                    created_at=int(account['created_at'].timestamp()),
                )
                for account in accounts_t.result()
            ],
            authorizations=[
                _application_proto(
                    app,
                    edit_user=edit_user,
                    authorized_at=token['authorized_at'],
                )
                for token in auths
                if (app := token.get('application')) is not None
                and app['client_id'] != SYSTEM_APP_PAT_CLIENT_ID
            ],
            applications=[
                _application_proto(
                    app,
                    edit_user=edit_user,
                    created_at=app['created_at'],
                )
                for app in apps_t.result()
            ],
            tokens=[
                Token(
                    id=token['id'],
                    name=token['name'],  # type: ignore
                    scopes=token['scopes'],
                    token_preview=token['token_preview'],
                    created_at=int(token['created_at'].timestamp()),
                    authorized_at=datetime_unix(token['authorized_at']),
                )
                for token in tokens_t.result()
            ],
        ),
        title_prefix=f'Users | {edit_user["display_name"]}',
    )


def _application_proto(
    app: OAuth2Application,
    *,
    edit_user: User,
    created_at: datetime | None = None,
    authorized_at: datetime | None = None,
):
    return Application(
        id=app['id'],
        name=app['name'],
        avatar_url=oauth2_app_avatar_url(app),
        client_id=app['client_id'],
        scopes=app['scopes'],
        owner=user_proto(
            edit_user if app['user_id'] == edit_user['id'] else app.get('user')
        ),
        created_at=datetime_unix(created_at),
        authorized_at=datetime_unix(authorized_at),
    )
