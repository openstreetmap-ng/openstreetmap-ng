from typing import Annotated

from fastapi import APIRouter, Cookie, Form, Response
from pydantic import SecretStr
from starlette import status

from app.config import MICROSOFT_OAUTH_PUBLIC
from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.openid import parse_openid_token_no_verify
from app.lib.render_response import render_response
from app.models.auth_provider import AuthProvider, AuthProviderAction
from app.queries.openid_query import OpenIDQuery
from app.services.auth_provider_service import AuthProviderService

router = APIRouter(prefix='/oauth2/microsoft')


@router.post('/authorize')
async def microsoft_authorize(
    action: Annotated[AuthProviderAction, Form()],
    referer: Annotated[str | None, Form()] = None,
):
    if not MICROSOFT_OAUTH_PUBLIC:
        return Response('Microsoft OAuth credentials are not configured', status.HTTP_503_SERVICE_UNAVAILABLE)
    openid = await OpenIDQuery.discovery('https://login.microsoftonline.com/common/v2.0')
    return AuthProviderService.continue_authorize(
        provider=AuthProvider.microsoft,
        action=action,
        referer=referer,
        redirect_uri=openid['authorization_endpoint'],
        redirect_params={
            'client_id': MICROSOFT_OAUTH_PUBLIC,
            'nonce': buffered_rand_urlsafe(16),
            'response_type': 'id_token',
            'response_mode': 'fragment',
            'scope': 'openid profile email',
        },
    )


@router.get('/callback')
async def get_microsoft_callback():
    return await render_response('oauth2/fragment_callback.jinja2')


@router.post('/callback')
async def post_microsoft_callback(
    id_token: Annotated[SecretStr, Form(min_length=1)],
    state: Annotated[str, Form(min_length=1)],
    auth_provider_state: Annotated[str, Cookie()],
):
    state_ = AuthProviderService.validate_state(
        provider=AuthProvider.microsoft,
        query_state=state,
        cookie_state=auth_provider_state,
    )
    payload = parse_openid_token_no_verify(id_token.get_secret_value())
    return await AuthProviderService.continue_callback(
        state=state_,
        uid=payload['sub'],
        name=payload.get('name'),
        email=payload.get('email'),
    )
