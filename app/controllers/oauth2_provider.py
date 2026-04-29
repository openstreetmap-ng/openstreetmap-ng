from typing import Annotated

from fastapi import APIRouter, Cookie, Form, HTTPException, Query
from pydantic import SecretStr
from starlette import status

from app.lib.auth_provider import resolve_code_identity, resolve_id_token_identity
from app.lib.render_response import render_response
from app.models.proto.settings_connections_types import Provider
from app.services.auth_provider_service import AuthProviderService

router = APIRouter(prefix='/oauth2')


@router.get('/{provider}/callback')
async def get_provider_callback(
    provider: Provider,
    auth_provider_state: Annotated[str | None, Cookie()] = None,
    code: Annotated[SecretStr | None, Query(min_length=1)] = None,
    state: Annotated[str | None, Query(min_length=1)] = None,
):
    if provider == 'microsoft':
        return await render_response('oauth2/fragment-callback')

    if code is None or state is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Missing callback parameters')
    if auth_provider_state is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, 'Missing callback state cookie'
        )

    state_ = AuthProviderService.validate_state(
        provider=provider,
        query_state=state,
        cookie_state=auth_provider_state,
    )
    identity = await resolve_code_identity(provider=provider, code=code)
    return await AuthProviderService.continue_callback(state=state_, **identity)


@router.post('/microsoft/callback')
async def post_microsoft_callback(
    id_token: Annotated[SecretStr, Form(min_length=1)],
    state: Annotated[str, Form(min_length=1)],
    auth_provider_state: Annotated[str, Cookie()],
):
    state_ = AuthProviderService.validate_state(
        provider='microsoft',
        query_state=state,
        cookie_state=auth_provider_state,
    )
    identity = resolve_id_token_identity(provider='microsoft', id_token=id_token)
    return await AuthProviderService.continue_callback(state=state_, **identity)
