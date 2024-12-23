import logging
from base64 import urlsafe_b64decode, urlsafe_b64encode
from time import time
from typing import cast

import cython
from fastapi import HTTPException
from starlette import status
from starlette.responses import RedirectResponse

from app.config import TEST_ENV
from app.lib.auth_context import auth_user
from app.lib.buffered_random import buffered_randbytes
from app.lib.crypto import hash_compare, hmac_bytes
from app.limits import AUTH_PROVIDER_STATE_MAX_AGE, AUTH_PROVIDER_VERIFICATION_MAX_AGE, COOKIE_AUTH_MAX_AGE
from app.models.auth_provider import AuthProvider, AuthProviderAction
from app.models.proto.server_pb2 import AuthProviderState, AuthProviderVerification
from app.queries.connected_account_query import ConnectedAccountQuery
from app.services.connected_account_service import ConnectedAccountService
from app.services.system_app_service import SystemAppService
from app.utils import extend_query_params, secure_referer


class AuthProviderService:
    @staticmethod
    def continue_authorize(
        *,
        provider: AuthProvider,
        action: AuthProviderAction,
        referer: str | None,
        redirect_uri: str,
        redirect_params: dict[str, str],
    ) -> RedirectResponse:
        state, hmac = _create_signed_state(
            provider=provider,
            action=action,
            referer=referer,
        )
        redirect_uri = extend_query_params(redirect_uri, {**redirect_params, 'state': hmac})
        response = RedirectResponse(redirect_uri, status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key='auth_provider_state',
            value=state,
            max_age=AUTH_PROVIDER_STATE_MAX_AGE,
            secure=not TEST_ENV,
            httponly=True,
            samesite='lax',
        )
        return response

    @staticmethod
    def validate_state(
        *,
        provider: AuthProvider,
        query_state: str,
        cookie_state: str,
    ) -> AuthProviderState:
        """
        Parse and validate an auth provider state.
        """
        buffer_b64 = cookie_state.encode()
        if not hash_compare(buffer_b64, urlsafe_b64decode(query_state), hash_func=hmac_bytes):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid state hmac')
        state = AuthProviderState.FromString(urlsafe_b64decode(buffer_b64))
        if state.timestamp + AUTH_PROVIDER_STATE_MAX_AGE < time():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Authorization timed out, please try again')
        if state.provider != provider.value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid state provider')
        return state

    @staticmethod
    async def continue_callback(
        *,
        state: AuthProviderState,
        uid: str | int,
        name: str | None,
        email: str | None,
    ) -> RedirectResponse:
        provider = AuthProvider(state.provider)
        action = cast(AuthProviderAction, state.action)
        uid = str(uid)

        if action == 'login':
            user_id = await ConnectedAccountQuery.find_user_id_by_auth_provider(provider, uid)
            if user_id is None:
                raise NotImplementedError  # TODO: handle not found
            logging.debug('Authenticated user %d using auth provider %r', user_id, provider)
            access_token = await SystemAppService.create_access_token('SystemApp.web', user_id=user_id)
            max_age = COOKIE_AUTH_MAX_AGE  # TODO: remember option for auth providers
            response = RedirectResponse(secure_referer(state.referer), status.HTTP_303_SEE_OTHER)
            response.delete_cookie('auth_provider_state')
            response.set_cookie(
                key='auth',
                value=access_token.get_secret_value(),
                max_age=max_age,
                secure=not TEST_ENV,
                httponly=True,
                samesite='lax',
            )
            return response

        elif action == 'settings':
            current_user = auth_user()
            if current_user is not None:
                user_id = await ConnectedAccountQuery.find_user_id_by_auth_provider(provider, uid)
                if user_id is None:
                    await ConnectedAccountService.add_connection(provider, uid)
                elif user_id != current_user.id:
                    raise NotImplementedError  # TODO: handle used by another user
            response = RedirectResponse('/settings/connections', status.HTTP_303_SEE_OTHER)
            response.delete_cookie('auth_provider_state')
            return response

        elif action == 'signup':
            user_id = await ConnectedAccountQuery.find_user_id_by_auth_provider(provider, uid)
            if user_id is not None:
                raise NotImplementedError  # TODO: handle used by another user
            verification = _create_signed_verification(
                provider=provider,
                uid=uid,
                name=name,
                email=email,
            )
            response = RedirectResponse('/signup', status.HTTP_303_SEE_OTHER)
            response.delete_cookie('auth_provider_state')
            response.set_cookie(
                key='auth_provider_verification',
                value=verification,
                max_age=AUTH_PROVIDER_VERIFICATION_MAX_AGE,
                secure=not TEST_ENV,
                httponly=True,
                samesite='lax',
            )
            return response

        raise NotImplementedError(f'Unsupported auth provider action {action!r}')

    @staticmethod
    def validate_verification(s: str | None) -> AuthProviderVerification | None:
        """
        Parse an auth provider verification string.

        Returns None if the verification is invalid or expired.
        """
        if not s:
            return None
        parts = s.encode().split(b'.', 1)
        if len(parts) != 2:
            return None  # malformed
        buffer_b64, hmac_b64 = parts
        if not hash_compare(buffer_b64, urlsafe_b64decode(hmac_b64), hash_func=hmac_bytes):
            return None  # invalid HMAC
        verification = AuthProviderVerification.FromString(urlsafe_b64decode(buffer_b64))
        if verification.timestamp + AUTH_PROVIDER_VERIFICATION_MAX_AGE < time():
            return None  # expired
        return verification


@cython.cfunc
def _create_signed_state(
    *,
    provider: AuthProvider,
    action: AuthProviderAction,
    referer: str | None,
) -> tuple[str, str]:
    """
    Create and sign an auth provider state.

    Returns a tuple of (state, hmac).
    """
    buffer_b64 = urlsafe_b64encode(
        AuthProviderState(
            timestamp=int(time()),
            provider=provider.value,
            action=action,
            referer=referer,
            nonce=buffered_randbytes(16),
        ).SerializeToString()
    )
    hmac_b64 = urlsafe_b64encode(hmac_bytes(buffer_b64))
    return buffer_b64.decode(), hmac_b64.decode()


@cython.cfunc
def _create_signed_verification(
    *,
    provider: AuthProvider,
    uid: str,
    name: str | None,
    email: str | None,
) -> str:
    """
    Create and sign an auth provider verification data.

    Returns a string of 'state.hmac'.
    """
    buffer_b64 = urlsafe_b64encode(
        AuthProviderVerification(
            timestamp=int(time()),
            provider=provider.value,
            uid=uid,
            name=name,
            email=email,
        ).SerializeToString()
    )
    hmac_b64 = urlsafe_b64encode(hmac_bytes(buffer_b64))
    return f'{buffer_b64.decode()}.{hmac_b64.decode()}'
