import logging

from fastapi import UploadFile
from sqlalchemy import func

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.locale import is_valid_locale
from app.lib.message_collector import MessageCollector
from app.lib.translation import t
from app.models.auth_provider import AuthProvider
from app.models.avatar_type import AvatarType
from app.models.db.user import User
from app.models.editor import Editor
from app.models.msgspec.user_token_struct import UserTokenStruct
from app.models.str import DisplayNameStr, EmailStr, PasswordStr
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.avatar_service import AvatarService
from app.services.email_change_service import EmailChangeService
from app.validators.email import validate_email_deliverability


class UserService:
    @staticmethod
    async def login(
        collector: MessageCollector,
        *,
        display_name_or_email: str,
        password: PasswordStr,
    ) -> UserTokenStruct:
        """
        Attempt to log in a user.

        Returns a new user session token.
        """

        user = await AuthService.authenticate_credentials(display_name_or_email, password)

        if user is None:
            collector.raise_error(None, t('users.auth_failure.invalid_credentials'))

        return await AuthService.create_session(user.id)

    @staticmethod
    async def update_about_me(
        *,
        description: str,
    ) -> None:
        """
        Update user's about me.
        """

        async with db_commit() as session:
            user = await session.get(User, auth_user().id, with_for_update=True)

            if user.description != description:
                user.description = description
                user.description_rich_hash = None

    @staticmethod
    async def update_avatar(
        avatar_type: AvatarType,
        avatar_file: UploadFile | None,
    ) -> str:
        """
        Update user's avatar.

        Returns the new avatar URL.
        """

        current_user = auth_user()

        # handle custom avatar
        if avatar_type == AvatarType.custom:
            avatar_id = await AvatarService.upload(avatar_file)
        else:
            avatar_id = None

        # update user data
        async with db_commit() as session:
            user = await session.get(User, current_user.id, with_for_update=True)
            old_avatar_id = user.avatar_id
            user.avatar_type = avatar_type
            user.avatar_id = avatar_id

        # cleanup old avatar
        if old_avatar_id is not None:
            await AvatarService.delete_by_id(old_avatar_id)

        return user.avatar_url

    @staticmethod
    async def update_settings(
        collector: MessageCollector,
        *,
        display_name: DisplayNameStr,
        editor: Editor | None,
        language: str,
        activity_tracking: bool,
        crash_reporting: bool,
    ) -> None:
        """
        Update user settings.
        """

        user = auth_user()

        # some early validation
        if not await UserRepository.check_display_name_available(display_name):
            collector.raise_error('display_name', t('user.display_name_already_taken'))

        # update user data
        async with db_commit() as session:
            user = await session.get(User, user.id, with_for_update=True)
            user.display_name = display_name
            user.editor = editor
            user.activity_tracking = activity_tracking
            user.crash_reporting = crash_reporting

            if is_valid_locale(language):
                user.language = language

    @staticmethod
    async def update_email(
        collector: MessageCollector,
        *,
        new_email: EmailStr,
        password: PasswordStr,
    ) -> None:
        """
        Update user email.

        Sends a confirmation email for the email change.
        """

        user = auth_user()

        # some early validation
        if user.email == new_email:
            return

        if not user.password_hasher.verify(user.password_hashed, user.password_salt, password):
            collector.raise_error('password', t('user.invalid_password'))
        if not await UserRepository.check_email_available(new_email):
            collector.raise_error('email', t('user.email_already_taken'))
        if not await validate_email_deliverability(new_email):
            collector.raise_error('email', t('user.invalid_email'))

        await EmailChangeService.send_confirm_email(new_email)
        collector.info('email', t('user.email_change_confirm_sent'))

    @staticmethod
    async def update_password(
        collector: MessageCollector,
        *,
        old_password: str,
        new_password: PasswordStr,
    ) -> None:
        """
        Update user password.
        """

        user = auth_user()
        password_hasher = user.password_hasher

        # some early validation
        if not password_hasher.verify(user.password_hashed, user.password_salt, old_password):
            collector.raise_error('old_password', t('user.invalid_password'))

        password_hashed = password_hasher.hash(new_password)

        # update user data
        async with db_commit() as session:
            user = await session.get(User, user.id, with_for_update=True)
            user.password_hashed = password_hashed
            user.password_changed_at = func.statement_timestamp()
            user.password_salt = None

        collector.success(None, t('user.password_changed'))
        logging.debug('Changed password for user %r', user.id)

    @staticmethod
    async def update_auth_provider(
        auth_provider: AuthProvider | None,
        auth_uid: str,
    ) -> None:
        """
        Update user auth provider.
        """

        # TODO: implement
        raise NotImplementedError
