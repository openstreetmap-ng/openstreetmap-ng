import logging
from typing import Literal

from app.config import ENV
from app.db import db, db_insert, db_update
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.lib.auth.password import PasswordLike
from app.lib.io.image import Image, UserAvatarType
from app.lib.standard.feedback import StandardFeedback
from app.lib.storage import AVATAR_STORAGE, BACKGROUND_STORAGE
from app.lib.text.locale import is_installed_locale
from app.lib.text.translation import t
from app.models.db.user import User, user_avatar_url, user_is_test
from app.models.db.user_profile import UserSocial
from app.models.types import DisplayName, Email, LocaleCode
from app.queries.user_query import UserQuery
from app.services.image_service import ImageService
from app.services.user_password_service import UserPasswordService
from app.services.user_token_email_service import UserTokenEmailService
from app.validators.email import validate_email_deliverability


class UserProfileService:
    @staticmethod
    async def update_avatar(
        *,
        preset: Literal['gravatar'] | None = None,
        avatar_file: bytes | None = None,
    ):
        """Update user's avatar. Returns the new avatar URL."""
        user = auth_user(required=True)
        user_id = user['id']
        old_avatar_id = user['avatar_id']

        avatar_type: UserAvatarType
        avatar_id = None
        if avatar_file is not None:
            avatar_type = 'custom'
            avatar_id = await ImageService.upload_avatar(avatar_file)
        else:
            avatar_type = preset

        await db_update(
            'user',
            {'avatar_type': avatar_type, 'avatar_id': avatar_id},
            where={'id': user_id},
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
    async def update_background(background_data: bytes):
        """Update user's background. Returns the new background URL."""
        user = auth_user(required=True)
        user_id = user['id']
        old_background_id = user['background_id']

        background_id = (
            await ImageService.upload_background(background_data)
            if background_data
            else None
        )

        await db_update(
            'user',
            {'background_id': background_id},
            where={'id': user_id},
        )

        # Cleanup old background
        if old_background_id is not None:
            await BACKGROUND_STORAGE.delete(old_background_id)

        return Image.get_background_url(background_id)

    @staticmethod
    async def update_description(
        *,
        description: str,
    ):
        """Update user's profile description."""
        user_id = auth_user(required=True)['id']
        value = description.strip() or None

        await db_insert(
            'user_profile',
            {'user_id': user_id, 'description': value},
            on_conflict=t"""(user_id) DO UPDATE SET
                description = EXCLUDED.description,
                description_rich_hash = NULL
                WHERE user_profile.description IS DISTINCT FROM EXCLUDED.description""",
        )

    @staticmethod
    async def update_socials(
        *,
        socials: list[UserSocial],
    ):
        """Update user's social links."""
        user_id = auth_user(required=True)['id']

        await db_insert(
            'user_profile',
            {'user_id': user_id, 'socials': socials},
            on_conflict=t"""(user_id) DO UPDATE SET
                socials = EXCLUDED.socials
                WHERE user_profile.socials != EXCLUDED.socials""",
        )

    @staticmethod
    async def update_settings(
        *,
        display_name: DisplayName,
        language: LocaleCode,
        activity_tracking: bool,
        crash_reporting: bool,
    ):
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
            await db_update(
                'user',
                {
                    'display_name': display_name,
                    'language': language,
                    'activity_tracking': activity_tracking,
                    'crash_reporting': crash_reporting,
                },
                where={'id': user_id},
                conn=conn,
            )
            if display_name != user['display_name']:
                await audit('change_display_name', conn, extra={'name': display_name})

    @staticmethod
    async def update_email(
        *,
        new_email: Email,
        password: PasswordLike,
    ):
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
    async def update_timezone(timezone: str):
        """Update the user timezone."""
        user_id = auth_user(required=True)['id']

        rowcount = await db_update(
            'user',
            {'timezone': timezone},
            where=t'id = {user_id} AND timezone != {timezone}',
        )

        if rowcount:
            logging.debug('Updated user %d timezone to %r', user_id, timezone)
