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

    entries = [
        AuthorizationsPage.Entry(
            application=AuthorizationsPage.Entry.Application(
                id=app['id'],
                name=app['name'],
                scopes=app['scopes'],
                avatar_url=oauth2_app_avatar_url(app),
                client_id=app['client_id'],
                owner=user_proto(app.get('user')),
            ),
            authorized_at=int(token['authorized_at'].timestamp()),  # type: ignore
        )
        for token in tokens
        if (app := token['application'])['client_id'] != SYSTEM_APP_PAT_CLIENT_ID  # type: ignore
    ]

    page_state = AuthorizationsPage(entries=entries)
    return await render_proto_page(
        page_state,
        title_prefix=t('settings.authorizations.title'),
    )


@router.get('/settings/applications/admin')
async def applications_admin(
    user: Annotated[User, web_user()],
):
    apps = await OAuth2ApplicationQuery.find_by_user(user['id'])
    page_state = AdminPage(
        entries=[
            AdminPage.Entry(
                id=app['id'],
                name=app['name'],
                scopes=app['scopes'],
                avatar_url=oauth2_app_avatar_url(app),
                created_at=int(app['created_at'].timestamp()),
            )
            for app in apps
        ]
    )

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
    page_state = TokensPage(
        tokens=[
            TokensPage.Token(
                id=token['id'],
                name=token['name'],  # type: ignore
                scopes=token['scopes'],
                token_preview=token['token_preview'],
                created_at=int(token['created_at'].timestamp()),
                authorized_at=datetime_unix(token['authorized_at']),
            )
            for token in tokens
        ],
        expanded_token_id=expand,
    )

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
