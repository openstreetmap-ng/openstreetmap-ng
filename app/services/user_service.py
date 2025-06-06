import logging

from fastapi import UploadFile
from pydantic import SecretStr

from app.config import ENV, USER_PENDING_EXPIRE, USER_SCHEDULED_DELETE_DELAY
from app.db import db
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.image import AvatarType, Image
from app.lib.locale import is_installed_locale
from app.lib.password_hash import PasswordHash
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.lib.user_token_struct_utils import UserTokenStructUtils
from app.models.db.oauth2_application import SYSTEM_APP_WEB_CLIENT_ID
from app.models.db.user import Editor, User, user_avatar_url, user_is_test
from app.models.types import DisplayName, Email, LocaleCode, Password
from app.queries.user_query import UserQuery
from app.queries.user_token_query import UserTokenQuery
from app.services.image_service import ImageService
from app.services.oauth2_token_service import OAuth2TokenService
from app.services.system_app_service import SystemAppService
from app.services.user_token_email_change_service import UserTokenEmailChangeService
from app.validators.email import validate_email, validate_email_deliverability


class UserService:
    @staticmethod
    async def login(
        *,
        display_name_or_email: DisplayName | Email,
        password: Password,
    ) -> SecretStr:
        """Attempt to login as a user. Returns a new user session token."""
        # TODO: normalize unicode & strip
        # (dot) indicates email format, display_name blacklists it
        if '.' in display_name_or_email:
            try:
                email = validate_email(display_name_or_email)
            except ValueError:
                user = None
            else:
                user = await UserQuery.find_one_by_email(email)
        else:
            display_name = DisplayName(display_name_or_email)
            user = await UserQuery.find_one_by_display_name(display_name)

        if user is None:
            logging.debug('User not found %r', display_name_or_email)
            StandardFeedback.raise_error(
                None, t('users.auth_failure.invalid_credentials')
            )

        user_id = user['id']
        verification = PasswordHash.verify(
            password_pb=user['password_pb'],
            password=password,
            is_test_user=user_is_test(user),
        )

        if not verification.success:
            logging.debug('Password mismatch for user %d', user_id)
            StandardFeedback.raise_error(
                None, t('users.auth_failure.invalid_credentials')
            )
        if verification.rehash_needed:
            await _rehash_user_password(user, password)
        if verification.schema_needed is not None:
            StandardFeedback.raise_error('password_schema', verification.schema_needed)

        logging.debug('Authenticated user %d using credentials', user_id)
        return await SystemAppService.create_access_token(
            SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
        )

    @staticmethod
    async def update_description(
        *,
        description: str,
    ) -> None:
        """Update user's profile description."""
        user = auth_user(required=True)
        user_id = user['id']

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET description = %s,
                    description_rich_hash = NULL
                WHERE id = %s AND description != %s
                """,
                (description, user_id, description),
            )

    @staticmethod
    async def update_avatar(avatar_type: AvatarType, avatar_file: UploadFile) -> str:
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
            await ImageService.delete_avatar_by_id(old_avatar_id)

        # noinspection PyTypeChecker
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
            await ImageService.delete_background_by_id(old_background_id)

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

        verification = PasswordHash.verify(
            password_pb=user['password_pb'],
            password=password,
            is_test_user=user_is_test(user),
        )

        if not verification.success:
            StandardFeedback.raise_error(
                'password', t('validation.password_is_incorrect')
            )
        if verification.rehash_needed:
            await _rehash_user_password(user, password)
        if verification.schema_needed is not None:
            StandardFeedback.raise_error('password_schema', verification.schema_needed)
        if not await UserQuery.check_email_available(new_email):
            StandardFeedback.raise_error(
                'email', t('validation.email_address_is_taken')
            )
        if not await validate_email_deliverability(new_email):
            StandardFeedback.raise_error('email', t('validation.invalid_email_address'))

        # TODO: send to old email too for security
        await UserTokenEmailChangeService.send_email(new_email)

    @staticmethod
    async def update_password(
        *,
        old_password: Password,
        new_password: Password,
    ) -> None:
        """Update user password."""
        user = auth_user(required=True)
        user_id = user['id']
        verification = PasswordHash.verify(
            password_pb=user['password_pb'],
            password=old_password,
            is_test_user=user_is_test(user),
        )

        if not verification.success:
            StandardFeedback.raise_error(
                'old_password', t('validation.password_is_incorrect')
            )
        if verification.schema_needed is not None:
            StandardFeedback.raise_error('password_schema', verification.schema_needed)

        new_password_pb = PasswordHash.hash(new_password)
        assert new_password_pb is not None, (
            'Provided password schemas cannot be used during update_password'
        )

        async with db(True) as conn:
            await conn.execute(
                """
                UPDATE "user"
                SET password_pb = %s,
                    password_updated_at = statement_timestamp()
                WHERE id = %s
                """,
                (new_password_pb, user_id),
            )

        logging.debug('Changed password for user %d', user_id)

    @staticmethod
    async def reset_password(
        token: SecretStr,
        *,
        new_password: Password,
        revoke_other_sessions: bool,
    ) -> None:
        """Reset the user password."""
        token_struct = UserTokenStructUtils.from_str(token)

        user_token = await UserTokenQuery.find_one_by_token_struct(
            'reset_password', token_struct
        )
        if user_token is None:
            raise_for.bad_user_token_struct()
        user_id = user_token['user_id']

        new_password_pb = PasswordHash.hash(new_password)
        assert new_password_pb is not None, (
            'Provided password schemas cannot be used during reset_password'
        )

        if revoke_other_sessions:
            await OAuth2TokenService.revoke_by_client_id(
                SYSTEM_APP_WEB_CLIENT_ID, user_id=user_id
            )

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT 1 FROM user_token
                WHERE id = %s AND type = 'reset_password'
                FOR UPDATE
                """,
                (token_struct.id,),
            ) as r:
                if await r.fetchone() is None:
                    raise_for.bad_user_token_struct()

            async with conn.pipeline():
                await conn.execute(
                    """
                    UPDATE "user"
                    SET password_pb = %s,
                        password_updated_at = DEFAULT
                    WHERE id = %s
                    """,
                    (new_password_pb, user_id),
                )
                await conn.execute(
                    """
                    DELETE FROM user_token
                    WHERE id = %s
                    """,
                    (token_struct.id,),
                )

        logging.debug('Reset password for user %d', user_id)

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


async def _rehash_user_password(user: User, password: Password) -> None:
    """Rehash user password if the hashing algorithm or parameters have changed."""
    user_id = user['id']

    new_password_pb = PasswordHash.hash(password)
    if new_password_pb is None:
        return

    async with db(True) as conn:
        result = await conn.execute(
            """
            UPDATE "user"
            SET password_pb = %s
            WHERE id = %s AND password_pb = %s
            """,
            (new_password_pb, user_id, user['password_pb']),
        )

        if result.rowcount:
            logging.debug('Rehashed password for user %d', user_id)
