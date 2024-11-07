from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Query
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import RedirectResponse

from app.config import API_URL
from app.lib.auth_context import web_user
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import (
    OAUTH_APP_NAME_MAX_LENGTH,
    OAUTH_PAT_LIMIT,
    OAUTH_PAT_NAME_MAX_LENGTH,
)
from app.models.db.oauth2_application import OAuth2Application
from app.models.db.oauth2_token import OAuth2Token
from app.models.db.user import User
from app.queries.oauth2_application_query import OAuth2ApplicationQuery
from app.queries.oauth2_token_query import OAuth2TokenQuery

router = APIRouter()


@router.get('/settings/applications')
async def applications_authorizations(
    user: Annotated[User, web_user()],
):
    with options_context(
        joinedload(OAuth2Token.application)  #
        .joinedload(OAuth2Application.user)
        .load_only(User.id, User.display_name, User.avatar_type, User.avatar_id),
    ):
        tokens = await OAuth2TokenQuery.find_unique_per_app_by_user_id(user.id)
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
    apps = await OAuth2ApplicationQuery.get_many_by_user_id(user.id)
    return await render_response(
        'settings/applications/admin.jinja2',
        {
            'apps': apps,
            'OAUTH_APP_NAME_MAX_LENGTH': OAUTH_APP_NAME_MAX_LENGTH,
        },
    )


@router.get('/settings/applications/admin/{id:int}/edit')
async def application_admin(
    id: PositiveInt,
    user: Annotated[User, web_user()],
):
    app = await OAuth2ApplicationQuery.find_one_by_id(id, user_id=user.id)
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
async def tokens(
    user: Annotated[User, web_user()],
    expand: Annotated[PositiveInt | None, Query()] = None,
):
    tokens = await OAuth2TokenQuery.find_many_pats_by_user(user_id=user.id, limit=OAUTH_PAT_LIMIT)
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
async def legacy_applications_admin():
    return RedirectResponse('/settings/applications/admin', status.HTTP_301_MOVED_PERMANENTLY)
