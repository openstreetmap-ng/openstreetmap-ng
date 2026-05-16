import logging
from asyncio import TaskGroup
from random import random
from typing import Any

from fastapi import Request
from pydantic import SecretStr

from app.config import ENV, USER_TOKEN_CLEANUP_PROBABILITY
from app.lib.audit import audit
from app.lib.auth.password import PasswordLike
from app.lib.standard.feedback import StandardFeedback
from app.lib.telemetry.testmethod import testmethod
from app.lib.text.translation import t
from app.middlewares.request_context_middleware import get_request
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import user_extend_scopes
from app.models.proto.auth_pb2 import LoginResponse, PasskeyAssertion
from app.models.scope import PUBLIC_SCOPES, Scope
from app.models.types import DisplayName, Email
from app.queries.oauth2_token_query import OAuth2TokenQuery
from app.queries.user_passkey_query import UserPasskeyQuery
from app.queries.user_query import UserQuery
from app.queries.user_recovery_code_query import UserRecoveryCodeQuery
from app.queries.user_totp_query import UserTOTPQuery
from app.services.system_app_service import SystemAppService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_password_service import UserPasswordService
from app.services.user_recovery_code_service import UserRecoveryCodeService
from app.services.user_token_service import UserTokenService
from app.services.user_totp_service import UserTOTPService

# default scopes when using session auth
_SESSION_AUTH_SCOPES: frozenset[Scope] = PUBLIC_SCOPES | {'web_user'}  # type: ignore
_EMPTY_SCOPES = frozenset[Scope]()


class AuthService:
    @staticmethod
    async def authenticate_request():
        """Authenticate the request. Returns the authenticated user (if any) and scopes."""
        req = get_request()
        path: str = req.url.path

        # Skip authentication for static requests
        if path.startswith('/static'):
            return None, _EMPTY_SCOPES, None

        # Try OAuth2 authentication for API endpoints
        if path.startswith(('/api/0.6/', '/api/0.7/', '/oauth2/')):
            r = await _authenticate_with_oauth2(req)
            if r is not None:
                return r

        # Try session cookie authentication
        r = await _authenticate_with_cookie(req)
        if r is not None:
            return r

        # Try test user authentication if in test environment
        if ENV != 'prod':
            r = await _authenticate_with_test_user(req)
            if r is not None:
                return r

        return None, _EMPTY_SCOPES, None

    @staticmethod
    async def authenticate_oauth2(access_token: SecretStr | None):
        """
        Authenticate a user with OAuth2.
        If param is None, it will be read from the request cookies.
        Returns None if the token is not found, or if it is not authorized.
        """
        if access_token is None:
            auth = get_request().cookies.get('auth')
            if auth is None:
                return None
            access_token = SecretStr(auth)
            del auth

        token = await OAuth2TokenQuery.find_authorized_by_token(access_token)
        if token is None or token['authorized_at'] is None:
            return None

        return token

    @staticmethod
    async def login(
        *,
        display_name_or_email: DisplayName | Email | None,
        password: PasswordLike | None,
        passkey: PasskeyAssertion | None,
        totp_code: int | None,
        recovery_code: str | None,
        bypass_2fa: bool = False,
    ):
        """Attempt to login as a user. Returns access_token or LoginResponse for 2FA."""
        if passkey is None:
            if display_name_or_email is None or password is None:
                StandardFeedback.raise_error(
                    None, t('users.auth_failure.invalid_credentials')
                )
            result = await _login_with_credentials(
                display_name_or_email,
                password,
                totp_code=totp_code,
                recovery_code=recovery_code,
                bypass_2fa=bypass_2fa,
            )
        else:
            # Mode 1 (passwordless): No credentials → require UV (PIN/biometric)
            # Mode 2 (2FA): Credentials provided → password already verified identity
            is_passwordless = display_name_or_email is None
            result = await _login_with_passkey(passkey, require_uv=is_passwordless)

        if isinstance(result, LoginResponse):
            return result

        access_token = await SystemAppService.create_access_token(
            SYSTEM_APP_WEB_CLIENT_ID, user_id=result
        )

        extra: dict[str, Any] = {'login': True}
        if passkey is not None:
            extra['2fa'] = 'passkey'
        elif recovery_code is not None:
            extra['2fa'] = 'recovery'
        elif totp_code is not None:
            extra['2fa'] = 'totp'
        if display_name_or_email is None:
            extra['passwordless'] = True

        audit(
            'auth_web',
            user_id=result,
            oauth2=(access_token.app_id, access_token.token_id),
            extra=extra,
            sample_rate=1,
            discard_repeated=None,
        ).close()

        # probabilistic cleanup of expired user tokens
        if random() < USER_TOKEN_CLEANUP_PROBABILITY:
            await UserTokenService.delete_expired()

        return access_token.token


# === Request authentication helpers ===


async def _extract_oauth2_token(request: Request):
    # Check in Authorization header
    authorization = request.headers.get('Authorization')
    if authorization:
        scheme, _, param = authorization.partition(' ')
        return SecretStr(param) if scheme.casefold() == 'bearer' and param else None

    # Check in form data
    if (
        request.method == 'POST'
        and request.headers.get('Content-Type') == 'application/x-www-form-urlencoded'
    ):
        value = (await request.form()).get('access_token')
        return SecretStr(value) if value and isinstance(value, str) else None

    return None


async def _authenticate_with_oauth2(request: Request):
    access_token = await _extract_oauth2_token(request)
    if access_token is None:
        return None

    logging.debug('Attempting to authenticate with OAuth2')
    token = await OAuth2TokenQuery.find_authorized_by_token_with_user(access_token)
    if token is None:
        return None

    user = token['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    scopes = user_extend_scopes(user, frozenset(token['scopes']))
    oauth2 = (token['application_id'], token['id'])
    audit('auth_api', user_id=token['user_id'], oauth2=oauth2).close()
    return user, scopes, oauth2


async def _authenticate_with_cookie(request: Request):
    auth = request.cookies.get('auth')
    if auth is None:
        return None
    access_token = SecretStr(auth)
    del auth

    logging.debug('Attempting to authenticate with cookies')
    token = await OAuth2TokenQuery.find_authorized_by_token_with_user(access_token)
    if token is None or token['scopes'] != ['web_user']:
        return None

    user = token['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    scopes = user_extend_scopes(user, _SESSION_AUTH_SCOPES)
    oauth2 = (token['application_id'], token['id'])
    audit('auth_web', user_id=token['user_id'], oauth2=oauth2).close()
    return user, scopes, oauth2


@testmethod
async def _authenticate_with_test_user(request: Request):
    authorization = request.headers.get('Authorization')
    if authorization is None:
        return None

    scheme, _, param = authorization.partition(' ')
    if scheme.casefold() != 'user':
        return None

    logging.debug('Attempting to authenticate with test user %r', param)
    user_display_name = DisplayName(param)
    user = await UserQuery.find_by_display_name(user_display_name)
    assert user is not None

    scopes = user_extend_scopes(user, _SESSION_AUTH_SCOPES)
    return user, scopes, None


# === Login helpers ===


async def _login_with_passkey(passkey: PasskeyAssertion, *, require_uv: bool):
    """Authenticate via passkey."""
    result = await UserPasskeyService.verify_passkey(passkey, require_uv=require_uv)
    if result is None:
        StandardFeedback.raise_error(None, t('users.auth_failure.invalid_credentials'))
    return result


async def _login_with_credentials(
    display_name_or_email: DisplayName | Email,
    password: PasswordLike,
    *,
    totp_code: int | None,
    recovery_code: str | None,
    bypass_2fa: bool,
):
    """
    Authenticate via password with 2FA handling.

    Returns user_id if authentication succeeds.
    Returns LoginResponse if additional 2FA step required.
    """
    user = await UserQuery.find_by_display_name_or_email(display_name_or_email)
    if user is None:
        logging.debug('User not found %r', display_name_or_email)
        StandardFeedback.raise_error(None, t('users.auth_failure.invalid_credentials'))

    await UserPasswordService.verify_password(
        user,
        password,
        error_message=lambda: t('users.auth_failure.invalid_credentials'),
        audit_failure='password',
    )

    user_id = user['id']

    # Check recovery code bypasses all 2FA
    if recovery_code is not None:
        if not await UserRecoveryCodeService.verify_recovery_code(
            user_id, recovery_code
        ):
            StandardFeedback.raise_error(
                'recovery_code',
                t('two_fa.invalid_or_expired_authentication_code'),
            )
        return user_id

    # Either passkey or TOTP is required
    # When both are configured, prefer passkey
    async with TaskGroup() as tg:
        has_passkey_t = tg.create_task(UserPasskeyQuery.check_any_by_user_id(user_id))
        has_recovery_t = tg.create_task(
            UserRecoveryCodeQuery.check_any_by_user_id(user_id)
        )
        totp = await UserTOTPQuery.find_one_by_user_id(user_id)

        if totp is not None and totp_code is not None:
            has_passkey_t.cancel()
            has_recovery_t.cancel()
            if not await UserTOTPService.verify_totp(user_id, totp_code):
                StandardFeedback.raise_error(
                    'totp_code',
                    t('two_fa.invalid_or_expired_authentication_code'),
                )
            return user_id

    resp = LoginResponse()
    if has_passkey_t.result():
        resp.passkey = True
    if totp is not None:
        resp.totp = totp['digits']
    if resp.ByteSize() and not (bypass_2fa and ENV != 'prod'):
        if has_recovery_t.result():
            resp.recovery = True
        logging.debug('2FA required for user %d', user_id)
        return resp

    return user_id
