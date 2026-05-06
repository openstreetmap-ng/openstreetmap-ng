from typing import Annotated

from fastapi import APIRouter, Query
from starlette import status
from starlette.responses import RedirectResponse

from app.config import OAUTH_PAT_LIMIT
from app.lib.auth_context import web_user
from app.lib.date_utils import datetime_unix
from app.lib.render_response import render_proto_page
from app.lib.translation import t
from app.models.db.oauth2_application import (
    SYSTEM_APP_PAT_CLIENT_ID,
    oauth2_app_avatar_url,
)
from app.models.db.user import User, user_proto
from app.models.proto.settings_applications_pb2 import (
    AdminPage,
    AuthorizationsPage,
    EditPage,
    TokensPage,
)
from app.models.types import ApplicationId, OAuth2TokenId
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/settings/applications')
async def applications_authorizations(
    user: Annotated[User, web_user()],
):
    tokens = await OAuth2TokenQuery.find_unique_per_app_by_user(user['id'])
    apps = await OAuth2ApplicationQuery.resolve_applications(tokens)
    await UserQuery.resolve_users(apps)

    page_state = AuthorizationsPage()
    for token in tokens:
        app = token['application']  # type: ignore
        if app['client_id'] == SYSTEM_APP_PAT_CLIENT_ID:
            continue
        entry = page_state.entries.add()
        entry.id = app['id']
        entry.name = app['name']
        entry.scopes.extend(app['scopes'])
        entry.avatar_url = oauth2_app_avatar_url(app)
        entry.client_id = app['client_id']
        if (owner := user_proto(app.get('user'))) is not None:
            entry.owner.CopyFrom(owner)
        entry.authorized_at = int(token['authorized_at'].timestamp())  # type: ignore
    return await render_proto_page(
        page_state,
        title_prefix=t('settings.authorizations.title'),
    )


@router.get('/settings/applications/admin')
async def applications_admin(
    user: Annotated[User, web_user()],
):
    apps = await OAuth2ApplicationQuery.find_by_user(user['id'])
    page_state = AdminPage()
    for app in apps:
        entry = page_state.entries.add()
        entry.id = app['id']
        entry.name = app['name']
        entry.scopes.extend(app['scopes'])
        entry.avatar_url = oauth2_app_avatar_url(app)
        entry.created_at = int(app['created_at'].timestamp())

    return await render_proto_page(
        page_state,
        title_prefix=t('settings.my_applications.title'),
    )


@router.get('/settings/applications/admin/{id:int}/edit')
async def application_admin(
    id: ApplicationId,
    user: Annotated[User, web_user()],
):
    app = await OAuth2ApplicationQuery.find_by_id(id, user_id=user['id'])
    if app is None:
        return RedirectResponse(
            '/settings/applications/admin', status.HTTP_303_SEE_OTHER
        )

    page_state = EditPage(
        id=app['id'],
        name=app['name'],
        scopes=app['scopes'],
        client_id=app['client_id'],
        avatar_url=oauth2_app_avatar_url(app),
        client_secret_preview=app['client_secret_preview'],
        confidential=app['confidential'],
        redirect_uris=app['redirect_uris'],
    )

    return await render_proto_page(
        page_state,
        title_prefix=t('settings.my_applications.title_name', name=app['name']),
    )


@router.get('/settings/applications/tokens')
async def get_tokens(
    user: Annotated[User, web_user()],
    expand: Annotated[OAuth2TokenId | None, Query()] = None,
):
    tokens = await OAuth2TokenQuery.find_pats_by_user(user['id'], limit=OAUTH_PAT_LIMIT)
    page_state = TokensPage(expanded_token_id=expand)
    for token in tokens:
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
        title_prefix=t('settings.my_tokens.title'),
    )


@router.get('/oauth2/authorized_applications')
async def legacy_applications_authorizations():
    return RedirectResponse('/settings/applications', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/oauth2/applications{_:path}')
async def legacy_applications_admin(_):
    return RedirectResponse(
        '/settings/applications/admin', status.HTTP_301_MOVED_PERMANENTLY
    )
