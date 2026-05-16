from asyncio import TaskGroup
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Response
from starlette import status

from app.lib.audit import audit
from app.lib.auth.context import web_user
from app.lib.render.proto import render_proto_page
from app.lib.time.date_utils import datetime_unix
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
    EditPage,
    Page,
)
from app.models.proto.settings_applications_pb2 import Application
from app.models.types import UserId
from app.queries.connected_account_query import ConnectedAccountQuery
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

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

    page_state = EditPage()
    page_state.account.id = edit_user['id']
    page_state.account.display_name = edit_user['display_name']
    page_state.account.avatar_url = user_avatar_url(edit_user)
    page_state.account.email = edit_user['email']
    page_state.account.email_verified = edit_user['email_verified']
    page_state.account.roles.extend(edit_user['roles'])
    page_state.account.created_at = int(edit_user['created_at'].timestamp())
    if (
        scheduled_delete_at := datetime_unix(edit_user['scheduled_delete_at'])
    ) is not None:
        page_state.account.scheduled_delete_at = scheduled_delete_at
    page_state.account.deleted = user_is_deleted(edit_user)

    page_state.two_factor_status.has_passkeys = tfa_status['has_passkeys']
    page_state.two_factor_status.has_totp = tfa_status['has_totp']
    page_state.two_factor_status.has_recovery = tfa_status['has_recovery']

    for account in accounts_t.result():
        connected_account = page_state.connected_accounts.add()
        connected_account.provider = account['provider']
        connected_account.uid = account['uid']
        connected_account.created_at = int(account['created_at'].timestamp())

    for token in auths:
        app = token.get('application')
        if app is None or app['client_id'] == SYSTEM_APP_PAT_CLIENT_ID:
            continue
        _application_proto(
            page_state.authorizations.add(),
            app,
            edit_user=edit_user,
            authorized_at=token['authorized_at'],
        )

    for app in apps_t.result():
        _application_proto(
            page_state.applications.add(),
            app,
            edit_user=edit_user,
            created_at=app['created_at'],
        )

    for token in tokens_t.result():
        page_token = page_state.tokens.add()
        page_token.id = token['id']
        page_token.name = token['name']  # type: ignore
        page_token.scopes.extend(token['scopes'])
        if token['token_preview'] is not None:
            page_token.token_preview = token['token_preview']
        page_token.created_at = int(token['created_at'].timestamp())
        if (authorized_at := datetime_unix(token['authorized_at'])) is not None:
            page_token.authorized_at = authorized_at

    return await render_proto_page(
        page_state,
        title_prefix=f'Users | {edit_user["display_name"]}',
    )


def _application_proto(
    result: Application,
    app: OAuth2Application,
    *,
    edit_user: User,
    created_at: datetime | None = None,
    authorized_at: datetime | None = None,
):
    result.id = app['id']
    result.name = app['name']
    result.avatar_url = oauth2_app_avatar_url(app)
    result.client_id = app['client_id']
    result.scopes.extend(app['scopes'])
    owner = user_proto(
        edit_user if app['user_id'] == edit_user['id'] else app.get('user')
    )
    if owner is not None:
        result.owner.CopyFrom(owner)
    if (created_at_unix := datetime_unix(created_at)) is not None:
        result.created_at = created_at_unix
    if (authorized_at_unix := datetime_unix(authorized_at)) is not None:
        result.authorized_at = authorized_at_unix
