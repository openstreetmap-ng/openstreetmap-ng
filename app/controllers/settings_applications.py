from asyncio import TaskGroup
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Query
from starlette import status
from starlette.responses import RedirectResponse

from app.config import API_URL
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.limits import (
    OAUTH_APP_NAME_MAX_LENGTH,
    OAUTH_PAT_LIMIT,
    OAUTH_PAT_NAME_MAX_LENGTH,
)
from app.models.db.oauth2_application import ApplicationId
from app.models.db.oauth2_token import OAuth2TokenId
from app.models.db.user import User
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/settings/applications')
async def applications_authorizations(
    user: Annotated[User, web_user()],
):
    tokens = await OAuth2TokenQuery.find_unique_per_app_by_user_id(user['id'])

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(tokens))
        tg.create_task(OAuth2ApplicationQuery.resolve_applications(tokens))

    return await render_response(
        'settings/applications/authorizations.jinja2',
        {
            'tokens': tokens,
        },
    )


@router.get('/settings/applications/admin')
async def applications_admin(
    user: Annotated[User, web_user()],
):
    apps = await OAuth2ApplicationQuery.get_many_by_user_id(user['id'])

    return await render_response(
        'settings/applications/admin.jinja2',
        {
            'apps': apps,
            'OAUTH_APP_NAME_MAX_LENGTH': OAUTH_APP_NAME_MAX_LENGTH,
        },
    )


@router.get('/settings/applications/admin/{id:int}/edit')
async def application_admin(
    id: ApplicationId,
    user: Annotated[User, web_user()],
):
    app = await OAuth2ApplicationQuery.find_one_by_id(id, user_id=user['id'])
    if app is None:
        return RedirectResponse('/settings/applications/admin', status.HTTP_303_SEE_OTHER)

    return await render_response(
        'settings/applications/edit.jinja2',
        {
            'app': app,
            'OAUTH_APP_NAME_MAX_LENGTH': OAUTH_APP_NAME_MAX_LENGTH,
        },
    )


@router.get('/settings/applications/tokens')
async def get_tokens(
    user: Annotated[User, web_user()],
    expand: Annotated[OAuth2TokenId | None, Query()] = None,
):
    tokens = await OAuth2TokenQuery.find_many_pats_by_user(user['id'], limit=OAUTH_PAT_LIMIT)

    return await render_response(
        'settings/applications/tokens.jinja2',
        {
            'expand_id': expand,
            'tokens': tokens,
            'API_HOST': urlsplit(API_URL).netloc,
            'API_URL': API_URL,
            'OAUTH_PAT_NAME_MAX_LENGTH': OAUTH_PAT_NAME_MAX_LENGTH,
        },
    )


@router.get('/oauth2/authorized_applications')
async def legacy_applications_authorizations():
    return RedirectResponse('/settings/applications', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/oauth2/applications{_:path}')
async def legacy_applications_admin(_):
    return RedirectResponse('/settings/applications/admin', status.HTTP_301_MOVED_PERMANENTLY)
