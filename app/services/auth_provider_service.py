import logging
from base64 import urlsafe_b64decode, urlsafe_b64encode
from time import time
from typing import assert_never

import cython
from fastapi import HTTPException
from starlette import status
from starlette.responses import RedirectResponse

from app.config import (
    AUTH_PROVIDER_STATE_MAX_AGE,
    AUTH_PROVIDER_VERIFICATION_MAX_AGE,
    COOKIE_AUTH_MAX_AGE,
)
from app.lib.auth_context import auth_user
from app.lib.auth_provider import get_authorize_redirect
from app.lib.cookie import (
    delete_cookie,
    set_auth_cookie,
    set_cookie,
)
from app.lib.crypto import hash_compare, hmac_bytes
from app.lib.referrer import secure_referrer
from app.lib.render_response import render_proto_page
from app.lib.translation import t
from app.models.db.connected_account import AuthProviderAction
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.proto.auth_provider_pb2 import AccountNotFoundPage, Action, Identity
from app.models.proto.server_pb2 import AuthProviderState, AuthProviderVerification
from app.models.proto.settings_connections_pb2 import Provider as ProviderEnum
from app.models.proto.settings_connections_types import Provider
from app.queries.connected_account_query import ConnectedAccountQuery
from app.services.audit_service import audit
from app.services.connected_account_service import ConnectedAccountService
from app.services.system_app_service import SystemAppService
from app.utils import extend_query_params
from speedup import buffered_randbytes


class AuthProviderService:
    @staticmethod
    async def start_authorize(
        *,
        provider: Provider,
        action: AuthProviderAction,
        referer: str | None,
    ):
        redirect_uri, redirect_params = await get_authorize_redirect(provider)
        state, hmac = _create_signed_state(
            provider=provider,
            action=action,
            referer=referer,
        )
        redirect_uri = extend_query_params(
            redirect_uri, {**redirect_params, 'state': hmac}
        )
        response = RedirectResponse(redirect_uri, status.HTTP_303_SEE_OTHER)
        set_cookie(
            response, 'auth_provider_state', state, max_age=AUTH_PROVIDER_STATE_MAX_AGE
        )
        return response

    @staticmethod
    def validate_state(
        *,
        provider: Provider,
        query_state: str,
        cookie_state: str,
    ):
        """Parse and validate an auth provider state."""
        buffer_b64 = cookie_state.encode()
        if not hash_compare(
            buffer_b64, urlsafe_b64decode(query_state), hash_func=hmac_bytes
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid state hmac')

        state = AuthProviderState.FromString(urlsafe_b64decode(buffer_b64))
        if state.issued_at + AUTH_PROVIDER_STATE_MAX_AGE.total_seconds() < time():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, 'Authorization timed out, please try again'
            )
        if state.provider != ProviderEnum.Value(provider):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Invalid state provider')

        return state

    @staticmethod
    async def continue_callback(
        *,
        state: AuthProviderState,
        uid: str | int,
        name: str | None,
        email: str | None,
    ):
        provider = ProviderEnum.Name(state.provider)
        action = Action.Name(state.action)
        uid = str(uid)

        if action == 'login':
            user_id = await ConnectedAccountQuery.find_user_id_by_auth_provider(
                provider, uid
            )
            if user_id is None:
                return await render_proto_page(
                    AccountNotFoundPage(provider=provider),
                    title_prefix=t('oauth.account_not_found'),
                )

            audit(
                'auth_web',
                user_id=user_id,
                extra={'login': True, 'provider': provider},
                sample_rate=1,
                discard_repeated=None,
            ).close()

            access_token = await SystemAppService.create_access_token(
                SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
            )
            response = RedirectResponse(
                secure_referrer(state.referer), status.HTTP_303_SEE_OTHER
            )
            delete_cookie(response, 'auth_provider_state')
            set_auth_cookie(response, access_token.token, max_age=COOKIE_AUTH_MAX_AGE)
            return response

        if action == 'settings':
            current_user = auth_user()
            if current_user is not None:
                user_id = await ConnectedAccountQuery.find_user_id_by_auth_provider(
                    provider, uid
                )
                if user_id is None:
                    await ConnectedAccountService.add_connection(provider, uid)
                elif user_id != current_user['id']:
                    raise NotImplementedError  # TODO: handle used by another user

            response = RedirectResponse(
                '/settings/connections', status.HTTP_303_SEE_OTHER
            )
            delete_cookie(response, 'auth_provider_state')
            return response

        if action == 'signup':
            user_id = await ConnectedAccountQuery.find_user_id_by_auth_provider(
                provider, uid
            )
            if user_id is not None:
                raise NotImplementedError  # TODO: handle used by another user

            verification = _create_signed_verification(
                provider=provider,
                uid=uid,
                name=name,
                email=email,
            )
            response = RedirectResponse('/signup', status.HTTP_303_SEE_OTHER)
            delete_cookie(response, 'auth_provider_state')
            set_cookie(
                response,
                'auth_provider_verification',
                verification,
                max_age=AUTH_PROVIDER_VERIFICATION_MAX_AGE,
            )
            return response

        assert_never(action)

    @staticmethod
    def validate_verification(s: str | None):
        """
        Parse an auth provider verification string.

        Returns None if the verification is invalid or expired.
        """
        if not s:
            return None

        parts = s.encode().split(b'.', 1)
        if len(parts) != 2:
            logging.debug('Auth provider verification is malformed')
            return None

        buffer_b64, hmac_b64 = parts
        if not hash_compare(
            buffer_b64, urlsafe_b64decode(hmac_b64), hash_func=hmac_bytes
        ):
            logging.debug('Auth provider verification HMAC is invalid')
            return None

        verification = AuthProviderVerification.FromString(
            urlsafe_b64decode(buffer_b64)
        )
        verification_expires_at = (
            verification.issued_at + AUTH_PROVIDER_VERIFICATION_MAX_AGE.total_seconds()
        )
        if verification_expires_at < time():
            logging.debug('Auth provider verification is expired')
            return None

        logging.debug('Successful auth provider verification')
        return verification


@cython.cfunc
def _create_signed_state(
    *,
    provider: Provider,
    action: AuthProviderAction,
    referer: str | None,
):
    """
    Create and sign an auth provider state.

    Returns a tuple of (state, hmac).
    """
    buffer_b64 = urlsafe_b64encode(
        AuthProviderState(
            issued_at=int(time()),
            provider=ProviderEnum.Value(provider),
            action=Action.Value(action),
            referer=referer,
            nonce=buffered_randbytes(16),
        ).SerializeToString()
    )
    hmac_b64 = urlsafe_b64encode(hmac_bytes(buffer_b64))
    return buffer_b64.decode(), hmac_b64.decode()


@cython.cfunc
def _create_signed_verification(
    *,
    provider: Provider,
    uid: str,
    name: str | None,
    email: str | None,
):
    """
    Create and sign an auth provider verification data.

    Returns a string of 'state.hmac'.
    """
    buffer_b64 = urlsafe_b64encode(
        AuthProviderVerification(
            issued_at=int(time()),
            identity=Identity(
                provider=ProviderEnum.Value(provider),
                name=name,
                email=email,
            ),
            uid=uid,
        ).SerializeToString()
    )
    hmac_b64 = urlsafe_b64encode(hmac_bytes(buffer_b64))
    return f'{buffer_b64.decode()}.{hmac_b64.decode()}'
