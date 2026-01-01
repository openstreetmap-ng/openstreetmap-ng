import logging
from asyncio import TaskGroup
from collections.abc import Awaitable, Callable
from random import random
from typing import Any

from fastapi import UploadFile
from psycopg import AsyncConnection
from psycopg.sql import SQL, Composable
from pydantic import SecretStr

from app.config import (
    ENV,
    USER_PENDING_EXPIRE,
    USER_SCHEDULED_DELETE_DELAY,
    USER_TOKEN_CLEANUP_PROBABILITY,
)
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.image import Image, UserAvatarType
from app.lib.locale import is_installed_locale
from app.lib.standard_feedback import StandardFeedback
from app.lib.storage import AVATAR_STORAGE, BACKGROUND_STORAGE
from app.lib.translation import t
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import Editor, User, UserRole, user_avatar_url, user_is_test
from app.models.proto.shared_pb2 import LoginResponse, PasskeyAssertion
from app.models.types import DisplayName, Email, LocaleCode, Password, UserId
from app.queries.user_passkey_query import UserPasskeyQuery
from app.queries.user_query import UserQuery
from app.queries.user_recovery_code_query import UserRecoveryCodeQuery
from app.queries.user_totp_query import UserTOTPQuery
from app.services.audit_service import audit
from app.services.image_service import ImageService
from app.services.system_app_service import SystemAppService
from app.services.user_passkey_service import UserPasskeyService
from app.services.user_password_service import UserPasswordService
from app.services.user_recovery_code_service import UserRecoveryCodeService
from app.services.user_token_email_service import UserTokenEmailService
from app.services.user_token_service import UserTokenService
from app.services.user_totp_service import UserTOTPService
from app.validators.email import validate_email_deliverability


class UserService:
    @staticmethod
    async def login(
        *,
        display_name_or_email: DisplayName | Email | None,
        password: Password | None,
        passkey: bytes | None,
        totp_code: str | None,
        recovery_code: str | None,
        bypass_2fa: bool = False,
    ) -> SecretStr | LoginResponse:
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

        # probabilistic cleanup of expired user tokens
        if random() < USER_TOKEN_CLEANUP_PROBABILITY:
            await UserTokenService.delete_expired()

        extra: dict[str, Any] = {'login': True}
        if passkey is not None:
            extra['2fa'] = 'passkey'
        elif recovery_code is not None:
            extra['2fa'] = 'recovery'
        elif totp_code is not None:
            extra['2fa'] = 'totp'
        if display_name_or_email is None:
            extra['passwordless'] = True

        await audit(
            'auth_web',
            user_id=result,
            oauth2=(access_token.app_id, access_token.token_id),
            extra=extra,
            sample_rate=1,
            discard_repeated=None,
        )
        return access_token.token

    @staticmethod
    async def update_avatar(
        avatar_type: UserAvatarType, avatar_file: UploadFile
    ) -> str:
        """Update user's avatar. Returns the new avatar URL."""
        user = auth_user(required=True)
        user_id = user['id']
        old_avatar_id = user['avatar_id']

        data = await avatar_file.read()
        avatar_id = (
            await ImageService.upload_avatar(data)
            if data and avatar_type == 'custom'
            else None
        )

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET avatar_type = %s,
                    avatar_id = %s
                WHERE id = %s
                """,
                (avatar_type, avatar_id, user_id),
            )

        # Cleanup old avatar
        if old_avatar_id is not None:
            await AVATAR_STORAGE.delete(old_avatar_id)

        user: User = {
            **user,
            'avatar_type': avatar_type,
            'avatar_id': avatar_id,
        }

        return user_avatar_url(user)

    @staticmethod
    async def update_background(background_file: UploadFile) -> str | None:
        """Update user's background. Returns the new background URL."""
        user = auth_user(required=True)
        user_id = user['id']
        old_background_id = user['background_id']

        data = await background_file.read()
        background_id = await ImageService.upload_background(data) if data else None

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET background_id = %s
                WHERE id = %s
                """,
                (background_id, user_id),
            )

        # Cleanup old background
        if old_background_id is not None:
            await BACKGROUND_STORAGE.delete(old_background_id)

        return Image.get_background_url(background_id)

    @staticmethod
    async def update_settings(
        *,
        display_name: DisplayName,
        language: LocaleCode,
        activity_tracking: bool,
        crash_reporting: bool,
    ) -> None:
        """Update user settings."""
        if not await UserQuery.check_display_name_available(display_name):
            StandardFeedback.raise_error(
                'display_name', t('validation.display_name_is_taken')
            )
        if not is_installed_locale(language):
            StandardFeedback.raise_error('language', t('validation.invalid_value'))

        user = auth_user(required=True)
        user_id = user['id']
        if user_is_test(user) and display_name != user['display_name'] and ENV != 'dev':
            StandardFeedback.raise_error(
                'display_name', 'Changing test user display_name is disabled'
            )

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET display_name = %s,
                    language = %s,
                    activity_tracking = %s,
                    crash_reporting = %s
                WHERE id = %s
                """,
                (display_name, language, activity_tracking, crash_reporting, user_id),
            )
            if display_name != user['display_name']:
                await audit('change_display_name', conn, extra={'name': display_name})

    @staticmethod
    async def update_editor(
        editor: Editor | None,
    ) -> None:
        """Update default editor"""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET editor = %s
                WHERE id = %s
                """,
                (editor, user_id),
            )

    @staticmethod
    async def update_email(
        *,
        new_email: Email,
        password: Password,
    ) -> None:
        """Update user email. Sends a confirmation email for the email change."""
        user = auth_user(required=True)
        if user['email'] == new_email:
            StandardFeedback.raise_error('email', t('validation.new_email_is_current'))
        if user_is_test(user) and ENV != 'dev':
            StandardFeedback.raise_error(
                'email', 'Changing test user email is disabled'
            )

        await UserPasswordService.verify_password(
            user,
            password,
            field_name='password',
            error_message=lambda: t('validation.password_is_incorrect'),
        )

        if not await UserQuery.check_email_available(new_email):
            StandardFeedback.raise_error(
                'email', t('validation.email_address_is_taken')
            )
        if not await validate_email_deliverability(new_email):
            StandardFeedback.raise_error('email', t('validation.invalid_email_address'))

        # TODO: send to old email too for security
        await UserTokenEmailService.send_email(new_email)

    @staticmethod
    async def update_timezone(timezone: str) -> None:
        """Update the user timezone."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            result = await conn.execute(
                """
                UPDATE "user"
                SET timezone = %s
                WHERE id = %s AND timezone != %s
                """,
                (timezone, user_id, timezone),
            )

            if result.rowcount:
                logging.debug('Updated user %d timezone to %r', user_id, timezone)

    # TODO: UI
    @staticmethod
    async def request_scheduled_delete() -> None:
        """Request a scheduled deletion of the user."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET scheduled_delete_at = statement_timestamp() + %s
                WHERE id = %s AND scheduled_delete_at IS NULL
                """,
                (USER_SCHEDULED_DELETE_DELAY, user_id),
            )

    @staticmethod
    async def abort_scheduled_delete() -> None:
        """Abort a scheduled deletion of the user."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET scheduled_delete_at = NULL
                WHERE id = %s
                """,
                (user_id,),
            )

    @staticmethod
    async def delete_old_pending_users() -> None:
        """Find old pending users and delete them."""
        logging.debug('Deleting old pending users')

        async with db(True) as conn:
            await conn.execute(
                """
                DELETE FROM "user"
                WHERE NOT email_verified
                AND created_at < statement_timestamp() - %s
                """,
                (USER_PENDING_EXPIRE,),
            )

    @staticmethod
    async def admin_update_user(
        *,
        user_id: UserId,
        display_name: DisplayName | None,
        email: Email | None,
        email_verified: bool,
        new_password: Password | None,
        roles: list[UserRole],
    ) -> None:
        roles.sort()
        if 'administrator' in roles and 'moderator' in roles:
            StandardFeedback.raise_error(
                'roles', 'administrator and moderator roles cannot be used together'
            )

        user = await UserQuery.find_by_id(user_id)
        if user is None:
            StandardFeedback.raise_error(None, 'User not found')

        assignments: list[Composable] = []
        params: list[Any] = []
        audits: list[Callable[[AsyncConnection], Awaitable[None]]] = []

        if display_name is not None:
            if not await UserQuery.check_display_name_available(
                display_name, user=user
            ):
                StandardFeedback.raise_error(
                    'display_name', t('validation.display_name_is_taken')
                )
            if (
                user_is_test(user)
                and display_name != user['display_name']
                and ENV != 'dev'
            ):
                StandardFeedback.raise_error(
                    'display_name', 'Changing test user display_name is disabled'
                )

            assignments.append(SQL('display_name = %s'))
            params.append(display_name)
            audits.append(
                lambda conn: audit(
                    'change_display_name',
                    conn,
                    target_user_id=user_id,
                    extra={'name': display_name},
                )
            )

        audit_email_extra = {}

        if email is not None:
            if user['email'] == email:
                StandardFeedback.raise_error(
                    'email', t('validation.new_email_is_current')
                )
            if user_is_test(user) and ENV != 'dev':
                StandardFeedback.raise_error(
                    'email', 'Changing test user email is disabled'
                )
            if not await UserQuery.check_email_available(email, user=user):
                StandardFeedback.raise_error(
                    'email', t('validation.email_address_is_taken')
                )
            if not await validate_email_deliverability(email):
                StandardFeedback.raise_error(
                    'email', t('validation.invalid_email_address')
                )

            assignments.append(SQL('email = %s'))
            params.append(email)
            audit_email_extra['email'] = email

        if user['email_verified'] != email_verified:
            assignments.append(SQL('email_verified = %s'))
            params.append(email_verified)
            audit_email_extra['verified'] = email_verified

        if audit_email_extra:
            audits.append(
                lambda conn: audit(
                    'change_email',
                    conn,
                    target_user_id=user_id,
                    extra=audit_email_extra,
                )
            )

        if new_password is not None:
            audits.append(
                lambda conn: audit(
                    'change_password',
                    conn,
                    target_user_id=user_id,
                )
            )

        if user['roles'] != roles:
            assignments.append(SQL('roles = %s'))
            params.append(roles)
            audits.append(
                lambda conn: audit(
                    'change_roles',
                    conn,
                    target_user_id=user_id,
                    extra={'roles': roles},
                )
            )

        query = SQL('UPDATE "user" SET {} WHERE id = %s').format(
            SQL(', ').join(assignments)
        )
        params.append(user_id)

        async with db(True) as conn:
            if ENV != 'test':  # Prevent admin user updates on the test instance
                if assignments:
                    await conn.execute(query, params)
                if email is not None:
                    await UserTokenService.delete_all_for_user(conn, user_id)
                if new_password is not None:
                    await UserPasswordService.set_password_unsafe(
                        conn, user_id, new_password
                    )
            for op in audits:
                await op(conn)


async def _login_with_passkey(
    passkey: bytes, *, require_uv: bool
) -> UserId | LoginResponse:
    """Authenticate via passkey."""
    assertion = PasskeyAssertion.FromString(passkey)
    result = await UserPasskeyService.verify_passkey(assertion, require_uv=require_uv)
    if result is None:
        StandardFeedback.raise_error(None, t('users.auth_failure.invalid_credentials'))
    return result


async def _login_with_credentials(
    display_name_or_email: DisplayName | Email,
    password: Password,
    *,
    totp_code: str | None,
    recovery_code: str | None,
    bypass_2fa: bool,
) -> UserId | LoginResponse:
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
    if has_recovery_t.result():
        resp.recovery = True
    if resp.ByteSize() and not (bypass_2fa and ENV != 'prod'):
        logging.debug('2FA required for user %d', user_id)
        return resp

    return user_id
